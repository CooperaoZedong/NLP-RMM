#!/usr/bin/env python3
import os, json, re, argparse, pathlib, random, hashlib, time
from jsonschema import validate, ValidationError

PROVIDER = os.getenv("PROVIDER", "openai")  # "openai" or "bedrock"

def call_llm(system, user, temperature=0.3, top_p=0.95, max_tokens=1024):
    if PROVIDER == "openai":
        # pip install openai
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        rsp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL","gpt-4o-mini"),
            messages=[{"role":"system","content":system},
                      {"role":"user","content":user}],
            temperature=temperature, top_p=top_p, max_tokens=max_tokens
        )
        return rsp.choices[0].message.content
    elif PROVIDER == "bedrock":
        import boto3, json as _json
        br = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION","us-east-1"))
        model = os.getenv("BEDROCK_MODEL","anthropic.claude-3-5-sonnet-20240620-v1:0")
        # Anthropic format (messages API)
        body = _json.dumps({
            "anthropic_version":"bedrock-2023-05-31",
            "messages":[
                {"role":"system","content":[{"type":"text","text":system}]},
                {"role":"user","content":[{"type":"text","text":user}]}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p
        })
        rsp = br.invoke_model(modelId=model, body=body)
        out = _json.loads(rsp["body"].read())
        return "".join([c["text"] for c in out["output"]["content"]])
    else:
        raise SystemExit("Unsupported PROVIDER")

SYSTEM_PLANNER = (
 "You are a workflow planner for an RMM platform. "
 "Return a minimal, strictly valid .wfl JSON ONLY. No explanations."
)
SYSTEM_CRITIC = (
 "You are a strict validator. Given a request, a candidate .wfl JSON, "
 "and validation errors, return a corrected JSON ONLY."
)
SYSTEM_PARAPHRASE = (
 "Rewrite the following into a single-sentence RMM workflow request. "
 "Keep meaning; vary phrasing; avoid boilerplate. One sentence only."
)

USER_COMPILE_TMPL = """Action catalog (IDs, allow-list): {action_ids}
Schema summary: {schema_summary}

User request:
{request}

Output: JSON only."""
USER_CRITIC_TMPL = """User request:
{request}

Candidate JSON:
{candidate}

Validation errors:
{errors}

Return corrected JSON only."""
USER_PARAPHRASE_TMPL = """{seed_text}"""

# ----------------- Utils -----------------
def extract_json_block(text: str):
    i = text.find("{")
    if i < 0: raise ValueError("No JSON start")
    depth=0; end=None
    for j,ch in enumerate(text[i:], start=i):
        if ch=="{": depth+=1
        elif ch=="}":
            depth-=1
            if depth==0:
                end=j+1; break
    if end is None: raise ValueError("Unbalanced braces")
    return json.loads(text[i:end])

def canonical_json(obj):  # for dedup
    return json.dumps(obj, sort_keys=True, separators=(",",":"))

def norm_text(t: str):
    t = t.lower()
    t = re.sub(r"\s+"," ", t)
    t = re.sub(r"[^a-z0-9 ,.:;_\-/]","", t)
    return t.strip()

def schema_summary(schema):
    keys = list(schema.get("properties",{}).keys())
    return "Top-level keys: " + ", ".join(keys[:8]) + "."

def verbalize_seed(obj):
    name = (obj.get("Name") or "").strip()
    desc = (obj.get("Description") or "").strip()
    return (desc or name or "Create an RMM workflow.").strip()

def walk_steps(steps, allow):
    for s in steps:
        t = s.get("workflowStepType")
        if t == 0:
            aid = str(s.get("actionType") or s.get("action_id"))
            if aid not in allow:
                raise AssertionError(f"Unknown action id: {aid}")
        elif t == 2:
            walk_steps(s.get("positiveOutcome", []), allow)
            walk_steps(s.get("negativeOutcome", []), allow)

def semantic_validate(obj, allow):
    steps = obj.get("Steps", [])
    assert steps, "No steps"
    walk_steps(steps, allow)

# ----------------- Main pipeline -----------------
def generate(seed_dir, schema_path, catalog_path, out_dir, target_count=3000,
             max_paraphrases=5, temperature=0.35, top_p=0.95):
    os.makedirs(out_dir, exist_ok=True)
    schema = json.loads(pathlib.Path(schema_path).read_text(encoding="utf-8"))
    catalog = json.loads(pathlib.Path(catalog_path).read_text(encoding="utf-8"))
    allow = set([str(x) for x in catalog.get("allow_list", [])])

    # Load seeds (.wfl)
    seeds=[]
    for p in pathlib.Path(seed_dir).glob("*.wfl"):
        s = p.read_text(encoding="utf-8", errors="replace")
        i = s.find("{")
        if i<0: continue
        depth=0; end=None
        for j,ch in enumerate(s[i:], start=i):
            if ch=="{": depth+=1
            elif ch=="}":
                depth-=1
                if depth==0:
                    end=j+1; break
        if end is None: continue
        seeds.append(json.loads(s[i:end]))
    if not seeds:
        raise SystemExit("No seed .wfl found")

    pool=[]

    # 1) seed pairs (NL verbalization -> gold .wfl)
    for seed in seeds:
        req = verbalize_seed(seed)
        pool.append({"input": req, "output": seed})

    # 2) paraphrase each seed intent (teacher) -> compile to .wfl (teacher)
    summ = schema_summary(schema)
    ids = ", ".join(sorted(allow))
    random.shuffle(seeds)
    for seed in seeds:
        base = verbalize_seed(seed)
        # paraphrases
        paras=[]
        for _ in range(max_paraphrases):
            txt = call_llm(SYSTEM_PARAPHRASE, USER_PARAPHRASE_TMPL.format(seed_text=base),
                           temperature=0.6, top_p=0.95, max_tokens=120)
            txt = txt.strip().strip('"')
            if len(txt)>15:
                if norm_text(txt) not in {norm_text(p) for p in paras}:
                    paras.append(txt)
        # compile each paraphrase
        for pr in paras:
            user = USER_COMPILE_TMPL.format(action_ids=ids, schema_summary=summ, request=pr)
            gen = call_llm(SYSTEM_PLANNER, user, temperature=temperature, top_p=top_p, max_tokens=1200)
            try:
                obj = extract_json_block(gen)
                validate(instance=obj, schema=schema)
                semantic_validate(obj, allow)
                pool.append({"input": pr, "output": obj})
            except Exception as e:
                # one critic repair
                crit_user = USER_CRITIC_TMPL.format(request=pr, candidate=gen, errors=str(e))
                repaired = call_llm(SYSTEM_CRITIC, crit_user, temperature=0.1, top_p=0.9, max_tokens=1200)
                try:
                    obj = extract_json_block(repaired)
                    validate(instance=obj, schema=schema)
                    semantic_validate(obj, allow)
                    pool.append({"input": pr, "output": obj})
                except Exception:
                    pass
            if len(pool) >= target_count: break
        if len(pool) >= target_count: break

    # 3) de-dup
    seen=set(); dedup=[]
    for ex in pool:
        key = hashlib.sha256((norm_text(ex["input"])+"|"+canonical_json(ex["output"])).encode()).hexdigest()
        if key not in seen:
            dedup.append(ex); seen.add(key)

    # 4) split & write
    random.shuffle(dedup)
    n=len(dedup); val_n=max(min(200, n//20), 100)
    train, val = dedup[val_n:], dedup[:val_n]
    out_train = os.path.join(out_dir, "train.jsonl")
    out_val   = os.path.join(out_dir, "val.jsonl")
    with open(out_train,"w",encoding="utf-8") as f:
        for ex in train: f.write(json.dumps(ex, ensure_ascii=False)+"\n")
    with open(out_val,"w",encoding="utf-8") as f:
        for ex in val: f.write(json.dumps(ex, ensure_ascii=False)+"\n")
    print(f"Wrote {len(train)} train / {len(val)} val to {out_dir}")

if __name__=="__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed_dir", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--target_count", type=int, default=3000)
    ap.add_argument("--max_paraphrases", type=int, default=5)
    ap.add_argument("--temperature", type=float, default=0.35)
    ap.add_argument("--top_p", type=float, default=0.95)
    args = ap.parse_args()
    generate(args.seed_dir, args.schema, args.catalog, args.out_dir,
             args.target_count, args.max_paraphrases, args.temperature, args.top_p)
