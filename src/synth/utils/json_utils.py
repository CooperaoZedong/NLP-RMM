import json, re

_fence_re = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_tag_re   = re.compile(r"<json>\s*(\{.*?\})\s*</json>", re.DOTALL | re.IGNORECASE)

def _strip_line_comments_outside_strings(s: str) -> str:
    out, i, in_str, esc = [], 0, False, False
    while i < len(s):
        ch = s[i]
        if in_str:
            out.append(ch)
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            i += 1
        else:
            if ch == '"':
                in_str = True
                out.append(ch); i += 1
            elif ch == "/" and i+1 < len(s) and s[i+1] == "/":
                # skip until newline
                while i < len(s) and s[i] not in "\r\n": i += 1
            else:
                out.append(ch); i += 1
    return "".join(out)

def extract_json_block(text: str):
    # 1) Prefer <json>...</json>
    m = _tag_re.search(text)
    if m:
        cleaned = _strip_line_comments_outside_strings(m.group(1))
        return json.loads(cleaned)
    # 2) Then try fenced code ```json ... ```
    m = _fence_re.search(text)
    if m:
        cleaned = _strip_line_comments_outside_strings(m.group(1))
        return json.loads(cleaned)
    # 3) Fallback: naive first balanced {...}
    i = text.find("{")
    if i < 0:
        raise ValueError("No JSON start")
    depth=0; end=None
    for j,ch in enumerate(text[i:], start=i):
        if ch=="{": depth+=1
        elif ch=="}":
            depth-=1
            if depth==0:
                end=j+1; break
    if end is None:
        raise ValueError("Unbalanced braces")
    cleaned = _strip_line_comments_outside_strings(text[i:end])
    return json.loads(cleaned)

def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",",":"))

def norm_text(t: str):
    t = t.lower()
    t = re.sub(r"\s+"," ", t)
    t = re.sub(r"[^a-z0-9 ,.:;_\-/]","", t)
    return t.strip()
