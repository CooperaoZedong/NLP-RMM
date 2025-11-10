#!/usr/bin/env python3
import os, json, argparse, random, pathlib, time, logging
from jsonschema import validate

from synth.providers.openai_client import OpenAIClient
from synth.providers.bedrock_client import BedrockClient

from synth.seeds import load_seed_wfls, verbalize_seed
from synth.paraphrase import paraphrases
from synth.compile_wfl import compile_with_repair
from synth.utils.contracts import load_schema, load_catalog
from synth.dedupe import dedupe
from synth.utils.debug import setup_logging, JsonlSink

LOG = logging.getLogger("synth.main")

def load_config(path: str):
    import yaml
    return yaml.safe_load(open(path, "r", encoding="utf-8"))

def make_client(cfg):
    provider = cfg["provider"]
    gen = cfg["generation"]
    if provider == "openai":
        m = cfg["openai"]["model"]; max_tokens = cfg["openai"]["max_tokens"]
        return OpenAIClient(model=m, max_tokens=max_tokens)
    if provider == "bedrock":
        m = cfg["bedrock"]["model"]; reg = cfg["bedrock"]["region"]; max_tokens = cfg["bedrock"]["max_tokens"]
        return BedrockClient(model=m, region=reg, max_tokens=max_tokens)
    raise SystemExit("Unsupported provider")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="synth/configs/synth.config.yaml")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg.get("debug", {}).get("level", "INFO") if not args.verbose else "DEBUG")

    client = make_client(cfg)
    paths = cfg["paths"]; gen = cfg["generation"]; tgt = cfg["targets"]
    debug_cfg = cfg.get("debug", {})
    limits = cfg.get("limits", {})
    sample_every = int(debug_cfg.get("sample_every", 1))
    flush_every = int(debug_cfg.get("flush_every", 50))
    save_raw = bool(debug_cfg.get("save_raw_generations", True))
    debug_dir = pathlib.Path(debug_cfg.get("out_dir_debug", "datasets/synth_debug"))
    debug_dir.mkdir(parents=True, exist_ok=True)

    schema = load_schema(paths["schema"])
    allow  = load_catalog(paths["catalog"])
    seeds  = load_seed_wfls(paths["seed_dir"])
    if not seeds: raise SystemExit("No seed .wfl found")
    LOG.info("seeds loaded: %d", len(seeds))

    ok_sink   = JsonlSink((debug_dir / "ok.jsonl").as_posix(), flush_every)
    fail_sink = JsonlSink((debug_dir / "fail.jsonl").as_posix(), flush_every)
    evt_sink  = JsonlSink((debug_dir / "events.jsonl").as_posix(), flush_every)

    pool = []
    pairs = []
    # 1) seed pairs
    for s in seeds:
        req = verbalize_seed(s)
        # do not inlude seeds to dataset for testing
        # pool.append({"input": req, "output": s})

    # counters
    paraphrase_total = 0
    compile_ok = 0
    compile_fail = 0
    repair_ok = 0
    repair_fail = 0
    start = time.time()

    # 2) paraphrase + compile
    random.shuffle(seeds)
    for idx, s in enumerate(seeds, 1):
        base = verbalize_seed(s)
        paras = paraphrases(client, base,
                            k=tgt["max_paraphrases_per_seed"],
                            temperature=gen["paraphrase_temperature"],
                            top_p=gen["paraphrase_top_p"])
        paraphrase_total += len(paras)
        if idx % sample_every == 0:
            LOG.info("seed %d/%d base=%r paras=%d", idx, len(seeds), base[:80], len(paras))

        for pr in paras:
            try:
                out = compile_with_repair(
                    client, pr, schema, allow,
                    temperature=gen["temperature"], top_p=gen["top_p"],
                    max_repair_attempts=int(limits.get("max_repair_attempts", 1)),
                    debug_sink=evt_sink if save_raw else None
                )
                pairs.append({"prompt": pr, "chosen": out["chosen"], "rejected": out["rejected"], "reason": out["reason"]})
                pool.append({"input": pr, "output": out["chosen"]})
                compile_ok += 1
                ok_sink.write({"input": pr, "output": out["chosen"], "rejected": out["rejected"], "reason": out["reason"]})
            except Exception as e:
                compile_fail += 1
                raw_prev = getattr(e, "raw", None)
                fail_sink.write({
                    "input": pr,
                    "error": str(e)
                })
                # if repair attempts were made inside compile_with_repair, they are already logged to events
                if "repair succeeded" in str(e):
                    repair_ok += 1
                else:
                    repair_fail += 1
            if len(pool) >= tgt["target_count"]:
                break
        if len(pool) >= tgt["target_count"]:
            break

    # 3) dedupe
    before = len(pool)
    pool = dedupe(pool)
    after = len(pool)
    LOG.info("dedupe: %d -> %d (removed %d)", before, after, before - after)

    # 4) split & write
    out_dir = pathlib.Path(paths["out_dir"]); out_dir.mkdir(parents=True, exist_ok=True)
    random.shuffle(pool)
    random.shuffle(pairs)
    n=len(pool); val_n = max(min(200, n//20), 100)
    train, val = pool[val_n:], pool[:val_n]
    (out_dir/"train.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in train), encoding="utf-8")
    (out_dir/"val.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in val), encoding="utf-8")
    (out_dir/"pairs.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in pairs), encoding="utf-8")

    elapsed = time.time() - start
    LOG.info("DONE wrote %d train / %d val, %d DPO pairs to %s in %.1fs", len(train), len(val), len(pairs), out_dir, elapsed)
    LOG.info("STATS paraphrases=%d compile_ok=%d compile_fail=%d", paraphrase_total, compile_ok, compile_fail)
    LOG.info("STATS repair_ok=%d repair_fail=%d", repair_ok, repair_fail)

    ok_sink.close(); fail_sink.close(); evt_sink.close()

if __name__ == "__main__":
    main()
