import json, pathlib

def load_seed_wfls(seed_dir: str):
    seeds=[]
    for p in pathlib.Path(seed_dir).glob("*.wfl"):
        s = p.read_text(encoding="utf-8", errors="replace")
        i = s.find("{")
        if i < 0: continue
        depth=0; end=None
        for j,ch in enumerate(s[i:], start=i):
            if ch=="{": depth+=1
            elif ch=="}":
                depth-=1
                if depth==0:
                    end=j+1; break
        if end is None: continue
        seeds.append(json.loads(s[i:end]))
    return seeds

def verbalize_seed(obj: dict) -> str:
    name = (obj.get("Name") or "").strip()
    desc = (obj.get("Description") or "").strip()
    return (desc or name or "Create an RMM workflow.").strip()
