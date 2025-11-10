import json, random
from torch.utils.data import Dataset

def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

class SFTJsonl(Dataset):
    def __init__(self, path):
        self.rows = [json.loads(l) for l in open(path, "r", encoding="utf-8")]
    def __len__(self): return len(self.rows)
    def __getitem__(self, i):
        row = self.rows[i]
        out = canonical_json(row["output"])
        return dict(input=row["input"], output=out)
