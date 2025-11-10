import json, subprocess, tempfile, os, textwrap, torch
from transformers import TextStreamer

def render_prompt(inp):
    return (
        "You are an Automation Workflow Generator. Return ONE JSON object only between <json> and </json>.\n"
        f"<user>\n{inp}\n</user>\n<assistant>\n<json>\n"
    )

def call_validator(obj):
    # Reuse your tools/validate_wfl.py; assumes it reads JSON from stdin and returns 0 on success
    p = subprocess.run(["python", "tools/validate_wfl.py"], input=json.dumps(obj).encode(), capture_output=True)
    return p.returncode == 0

def eval_pass_rate(model, tok, val_rows, max_new_tokens=2000):
    model.eval()
    ok = 0
    for r in val_rows:
        prompt = render_prompt(r["input"])
        ids = tok(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=max_new_tokens, do_sample=False)
        text = tok.decode(out[0], skip_special_tokens=True)
        # Extract between <json>...</json>
        try:
            j = text.split("<json>")[1].split("</json>")[0]
            obj = json.loads(j)
            ok += 1 if call_validator(obj) else 0
        except Exception:
            pass
    return ok / len(val_rows)
