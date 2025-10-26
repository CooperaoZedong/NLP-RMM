import hashlib
from typing import Dict, Any, List
from synth.utils.json_utils import canonical_json, norm_text

def dedupe(pairs: List[Dict[str, Any]]):
    seen, out = set(), []
    for ex in pairs:
        key = hashlib.sha256((norm_text(ex["input"])+"|"+canonical_json(ex["output"])).encode()).hexdigest()
        if key not in seen:
            out.append(ex); seen.add(key)
    return out
