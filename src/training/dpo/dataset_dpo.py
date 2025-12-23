import json, os
from datasets import Dataset

def load_pairs(path):
    rows = load_jsonl_dir(path)
    exs = []
    for r in rows:
        exs.append({
            "prompt": r["prompt"],
            "chosen": json.dumps(r["chosen"], sort_keys=True),
            "rejected": json.dumps(r["rejected"], sort_keys=True)
        })
    return Dataset.from_list(exs)

def load_jsonl_dir(path):
    # SageMaker mounts single file; support either dir or file
    files = []
    if os.path.isdir(path):
        for n in os.listdir(path):
            if n.endswith(".jsonl"): files.append(os.path.join(path, n))
    else:
        files = [path]
    rows = []
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            rows.extend([json.loads(l) for l in fh])
    return rows
