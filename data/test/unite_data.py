#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from synth.utils.json_utils import canonical_json, norm_text

def dedupe(pairs: List[Dict[str, Any]], input_kw: str = "input", output_kw: str = "output"):
    seen, out = set(), []
    for ex in pairs:
        key = hashlib.sha256((norm_text(json.loads(ex)[input_kw])+"|"+canonical_json(json.loads(ex)[output_kw])).encode()).hexdigest()
        if key not in seen:
            out.append(ex); seen.add(key)
    return out

def main():
    ap = argparse.ArgumentParser(description="Aggregate separate train and validation datasets into a single dataset.")
    ap.add_argument("--workdir", required=True, help="Path to dataset directory")
    ap.add_argument("--artifact_num", required=True, help="Artifact quantity to be aggregated")
    args = ap.parse_args()

    workdir = Path(args.workdir)
    num_artifacts = int(args.artifact_num)

    train_buffer = []
    validate_buffer = []
    pairs_buffer = []

    for i in range(num_artifacts):
        input_path = workdir / f"train{i+1}.jsonl"
        with input_path.open("r", encoding="utf-8") as f:
            dataset_content = list(f)
            print("train last row:", dataset_content[:-1])
            train_buffer.extend(dataset_content)

        input_path = workdir / f"val{i+1}.jsonl"
        with input_path.open("r", encoding="utf-8") as f:
            dataset_content = list(f)
            print("val last row:", dataset_content[:-1])
            validate_buffer.extend(dataset_content)

        input_path = workdir / f"pairs{i+1}.jsonl"
        with input_path.open("r", encoding="utf-8") as f:
            dataset_content = list(f)
            print("pairs last row:", dataset_content[:-1])
            pairs_buffer.extend(dataset_content)

    print(f"Buffers lens before dedupe: train %s, validate %s, pairs %s", len(train_buffer), len(validate_buffer), len(pairs_buffer))
    train_buffer = dedupe(train_buffer, input_kw="input", output_kw="output")
    validate_buffer = dedupe(validate_buffer, input_kw="input", output_kw="output")
    pairs_buffer = dedupe(pairs_buffer, input_kw="prompt", output_kw="chosen")
    print("Buffers lens after dedupe: train %s, validate %s, pairs %s", len(train_buffer), len(validate_buffer), len(pairs_buffer))

    (workdir/"train.jsonl").write_text("".join(x for x in train_buffer), encoding="utf-8")
    (workdir/"val.jsonl").write_text("".join(x for x in validate_buffer), encoding="utf-8")
    (workdir/"pairs.jsonl").write_text("".join(x for x in pairs_buffer), encoding="utf-8")

if __name__ == "__main__":
    main()
