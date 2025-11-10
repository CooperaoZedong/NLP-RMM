import copy, logging
from datetime import datetime, timezone
from jsonschema import validate, ValidationError

from synth.prompts import SYSTEM_PLANNER, USER_COMPILE_TMPL, USER_SABOTAGER_TMPL, SYSTEM_CRITIC, SYSTEM_SABOTAGER, USER_CRITIC_TMPL, FEWSHOTS_TEXT
from synth.utils.json_utils import extract_json_block
from synth.utils.contracts import schema_summary
from synth.utils.semantic_validate import semantic_validate_workflow
from synth.utils.errors import SynthesisError

LOG = logging.getLogger("synth.compile")

def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")

def _coerce_aliases_and_normalize(obj: dict) -> dict:
    object = copy.deepcopy(obj)
    # top-level alias fixes
    if "Steps" in object and "workflowSteps" not in object:
        object["workflowSteps"] = object.pop("Steps")
    # schedule date normalization
    if isinstance(object.get("workflowSteps"), list) and object["workflowSteps"]:
        s0 = object["workflowSteps"][0]
        if s0.get("workflowStepType") == 1 and s0.get("triggerSubType") == "Scheduled":
            sch = s0.get("schedule") or {}
            if "startDate" not in sch or not isinstance(sch["startDate"], str):
                sch["startDate"] = _now_iso()
            if "timezone" not in sch or not isinstance(sch["timezone"], str):
                sch["timezone"] = "UTC"
            s0["schedule"] = sch
    return object

def build_user_prompt(request: str) -> str:
    return USER_COMPILE_TMPL.format(fewshots=FEWSHOTS_TEXT, request=request)

def compile_once(client, request: str, temperature: float, top_p: float) -> str:
    user = USER_SABOTAGER_TMPL.format(
        fewshots=FEWSHOTS_TEXT,
        request=request
    )
    return client.chat(SYSTEM_SABOTAGER, user, temperature=temperature, top_p=top_p)

def compile_with_repair(client, request: str, schema: dict, allow_ids: set, temperature: float, top_p: float,
                        max_repair_attempts: int = 1, debug_sink=None):
    user_prompt = build_user_prompt(request)
    raw = client.chat(SYSTEM_PLANNER, user_prompt, temperature=temperature, top_p=top_p)
    LOG.info("Raw gen: %s", raw)
    if "<json>" not in raw.lower():
    # quick format nudge (no semantic change)
        nudged = client.chat(
            "Return the SAME content as STRICT JSON only, wrapped in <json> and </json>. No prose.",
            "Reformat your previous answer.",
            temperature=0.0, top_p=1.0
        )
        if "<json>" in nudged.lower():
            raw = nudged

    LOG.info("extracted: %s", raw)
    try:
        obj = extract_json_block(raw)
        obj = _coerce_aliases_and_normalize(obj)
        obj2 = None
        reason = None
        validate(instance=obj, schema=schema)
        semantic_validate_workflow(obj)
        if debug_sink:
            debug_sink.write({"stage":"compile_ok","request":request,"raw_len":len(raw)})

        while True:
            try:
                rejected = compile_once(client, request, temperature=0.3, top_p=0.3)
                rejected = extract_json_block(rejected)
                rejected = _coerce_aliases_and_normalize(rejected)
                obj2 = rejected
                validate(instance=rejected, schema=schema)
                semantic_validate_workflow(rejected)

            except (ValidationError, AssertionError, ValueError) as e:
                err = str(e)
                if debug_sink:
                    debug_sink.write({"stage":"compile_rejected","request":request})
                reason = err
                break

        dpo_obj = {
            "chosen": obj,
            "rejected": obj2,
            "reason": reason,
            "prompt": user_prompt
        }
        return dpo_obj
    except (ValidationError, AssertionError, ValueError) as e:
        err = str(e)
        if debug_sink: debug_sink.write({"stage":"compile_fail","request":request,"error":err,"raw_preview":raw[:400]})
        # for attempt in range(max_repair_attempts):
        #     crit_user = USER_CRITIC_TMPL.format(request=request, candidate=raw, errors=err)
        #     repaired = client.chat(SYSTEM_CRITIC, crit_user, temperature=0.1, top_p=0.9)
        #     try:
        #         obj2 = extract_json_block(repaired)
        #         obj2 = _coerce_aliases_and_normalize(obj2)
        #         validate(instance=obj2, schema=schema)
        #         semantic_validate_workflow(obj2)
        #         if debug_sink:
        #             debug_sink.write({"stage":"repair_ok","request":request,"attempt":attempt+1,
        #                               "repaired_preview": repaired[:400]})
        #         LOG.info("repair succeeded on attempt=%d", attempt+1)
        #         return obj2
        #     except (ValidationError, AssertionError, ValueError) as e2:
        #         err = str(e2)
        #         LOG.warning("repair attempt=%d failed: %s", attempt+1, err)
        #         if debug_sink:
        #             debug_sink.write({"stage":"repair_fail","request":request,"attempt":attempt+1,
        #                               "error":err, "repaired_preview": repaired[:400]})
        #         raw = repaired
        raise SynthesisError(err, raw=raw)
