import json, sys, re, pathlib
from jsonschema import validate
from jsonschema.exceptions import ValidationError

SCHEMA_PATH = pathlib.Path("data/schema/wfl.schema.json")

def load_json_from_wfl(p: pathlib.Path):
    s = p.read_text(encoding="utf-8", errors="replace")
    i = s.find("{")
    if i < 0:
        raise ValueError(f"No JSON object found in {p}")
    depth = 0; end = None
    for j, ch in enumerate(s[i:], start=i):
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j + 1; break
    if end is None:
        raise ValueError(f"Unbalanced braces in {p}")
    return json.loads(s[i:end])

def main(dir_path):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    ok, fail = 0, 0
    for p in pathlib.Path(dir_path).glob("*.wfl"):
        try:
            obj = load_json_from_wfl(p)
            validate(instance=obj, schema=schema)
            print(f"[OK]   {p.name}")
            ok += 1
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            print(f"[FAIL] {p.name}: {e}")
            fail += 1
    print(f"\nSummary: {ok} valid, {fail} invalid")
    return 0 if fail == 0 else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))