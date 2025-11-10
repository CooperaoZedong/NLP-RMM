import json
from datasets import Dataset

def load_pairs(path):
    rows = [json.loads(l) for l in open(path, "r", encoding="utf-8")]
    exs = []
    for r in rows:
        exs.append({
            "prompt": r["prompt"],
            "chosen": json.dumps(r["chosen"], sort_keys=True),
            "rejected": json.dumps(r["rejected"], sort_keys=True)
        })
    return Dataset.from_list(exs)
