import json, logging, subprocess, tempfile, os, textwrap, torch
from collections import Counter
from jsonschema import validate
from synth.utils.semantic_validate import semantic_validate_workflow
from transformers import TextStreamer
LOG = logging.getLogger(__name__)

def render_prompt(inp):
    return (
        "You are an expert Workflow Template generator for an IT management platform (similar to RMM platform). Your goal is to produce valid, standards-compliant workflow templates in JSON format that integrate triggers, conditions, and actions. Return ONE JSON object only between <json> and </json>.\n"
        f"<user>\n{inp}\n</user>\n<assistant>\n<json>\n"
    )

def is_valid_workflow(obj) -> bool:
    """
    Combined structural + semantic validation for one workflow JSON object.
    Returns True if it passes all checks, False otherwise.
    """
    # 1) JSON Schema / structural validation
    try:
        validate(instance=obj, schema=schema)
    except Exception as e:
        LOG.debug("schema validation failed: %s", e)
        return False

    # 2) Semantic validation
    try:
        result = semantic_validate_workflow(obj)
        if result is False:
            LOG.debug("semantic validation returned False")
    except Exception as e:
        LOG.debug("semantic validation raised: %s", e)
        return False

    if isinstance(result, bool):
        return result

    if isinstance(result, tuple) and len(result) >= 1:
        ok = result[0]
        return bool(ok)

    return result is None

def eval_pass_rate(
        model,
        tok,
        val_rows,
        max_new_tokens: int = 2000,
        log_failures: bool = True,
        max_fail_logs: int = 20,
) -> float:
    """
    Run deterministic generation on val_rows and compute the fraction of
    outputs that:
      1) contain a <json>...</json> block
      2) parse as JSON
      3) pass schema + semantic validation.

    Logs reasons for failures (up to max_fail_logs examples).
    """
    model.eval()
    ok = 0
    stats = Counter()
    logged = 0

    for idx, r in enumerate(val_rows):
        prompt = render_prompt(r["input"])

        # 1) Generate
        try:
            ids = tok(prompt, return_tensors="pt").to(model.device)
            with torch.no_grad():
                out = model.generate(
                    **ids,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                )
            text = tok.decode(out[0], skip_special_tokens=True)
        except Exception as e:
            stats["generation_error"] += 1
            if log_failures and logged < max_fail_logs:
                LOG.warning(
                    "eval row %d: generation error: %s",
                    idx,
                    repr(e),
                )
                logged += 1
            continue

        # 2) Extract <json>...</json>
        start = text.find("<json>")
        end = text.find("</json>")
        if start == -1 or end == -1:
            stats["missing_json_tags"] += 1
            if log_failures and logged < max_fail_logs:
                print(
                    "eval row: missing <json> tags. snippet: ",
                    text[:300].replace("\n", " "),
                )
                logged += 1
            continue

        payload = text[start + len("<json>") : end].strip()
        if not payload:
            stats["empty_json_block"] += 1
            if log_failures and logged < max_fail_logs:
                print(
                    "eval row: empty <json> block. full_text_snippet: ",
                    text[:300].replace("\n", " "),
                )
                logged += 1
            continue

        # 3) JSON decode
        try:
            obj = json.loads(payload)
        except Exception as e:
            stats["json_parse_error"] += 1
            if log_failures and logged < max_fail_logs:
                print(
                    "eval row %d: json parse error:",
                    repr(e)
                )
                logged += 1
            continue

        # 4) Schema + semantic validation
        if not is_valid_workflow(obj):
            stats["validation_failed"] += 1
            if log_failures and logged < max_fail_logs:
                print(
                    "eval row: workflow failed validation. json_snippet: ",
                    payload[:300],
                )
                logged += 1
            continue

        # Passed all checks
        ok += 1

    total = len(val_rows) or 1  # avoid division by zero
    rate = ok / total

    # One summary line that you can regex on if you want a metric
    LOG.info(
        "eval_pass_rate=%.4f ok=%d total=%d failure_stats=%s",
        rate,
        ok,
        total,
        dict(stats),
    )

    print("failure stats: ", dict(stats))

    return rate

def eval_ce(model, tok, rows):
    # teacher-forced: measure logprob of reference outputs
    losses = []
    for row in rows:
        prompt = render_prompt(row["input"])         # same as training
        target = json.dumps(row["output"])          # reference JSON
        text = prompt + target

        tokens = tok(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model(**tokens, labels=tokens["input_ids"])
        losses.append(out.loss.item())
    return sum(losses) / len(losses)
