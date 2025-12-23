from typing import List, Protocol
import logging

from synth.prompts import SYSTEM_PARAPHRASE, USER_PARAPHRASE_TMPL
from synth.utils.json_utils import norm_text

LOG = logging.getLogger("synth.paraphrase")

DOMAIN_KEYWORDS = [
    "datto", "vsa", "vsax", "rmm", "workflow", "managed files",
    "bitlocker", "firewall", "smbv1", "registry",
    "psa", "ticket", "powershell", "msiexec",
]

VIEW_ROLES = ('intent', 'ops', 'policy', 'helpdesk')

class LLMClient(Protocol):
    def chat(self, system: str, user: str, temperature: float, top_p: float) -> str: ...


def key_terms(source: str):
    s = source.lower()
    return {k for k in DOMAIN_KEYWORDS if k in s}

# Jaccard similarity between two strings
def jaccard_similarity(src: str, target: str) -> float:
    s_src = set(src.lower().split())
    s_target = set(target.lower().split())
    if not s_src or not s_target:
        return 0.0
    return len(s_src & s_target) / len(s_src | s_target)

def is_bad_paraphrase(src: str, cand: str) -> bool:
    if bad_length_ratio(src, cand):
        LOG.info("paraphrase bad length ratio: src_len=%d cand_len=%d", len(src), len(cand))
        return True
    if missing_too_many_keywords(src, cand):
        LOG.info("paraphrase missing too many keywords")
        return True
    return False

def missing_too_many_keywords(source: str, cand: str) -> bool:
    src_terms = key_terms(source)
    if not src_terms:
        return False
    cand_lower = cand.lower()
    missing = [k for k in src_terms if k not in cand_lower]
    # allow dropping 1 term, but not most of them
    return len(missing) > max(1, 0.6 * len(src_terms))

def bad_length_ratio(src: str, cand: str) -> bool:
    ls, lc = len(src), len(cand)
    if lc < 20:
        return True
    ratio = lc / max(ls, 1)
    # Too short or too long relative to original
    return ratio < 0.5 or ratio > 10

def paraphrases(client: LLMClient, seed: dict, k: int, temperature: float, top_p: float) -> List[str]:
    outs, seen = [], set()
    attempted = 0
    for _ in range(k):
        for view in enumerate(VIEW_ROLES):
            role_idx, role_name = view
            system_prompt = SYSTEM_PARAPHRASE
            user_prompt = USER_PARAPHRASE_TMPL.format(
                input=role_name,
                goal=seed['primary_goal'],
                scope=seed['os_scope']
            )
            try:
                resp = client.chat(
                    system=system_prompt,
                    user=user_prompt,
                    temperature=temperature,
                    top_p=top_p
                )
                print("Paraphrase response:", resp)
                attempted += 1
                paraphrased = norm_text(resp)
                if paraphrased in seen:
                    continue
                if is_bad_paraphrase(seed['primary_goal'], paraphrased):
                    continue
                seen.add(paraphrased)
                outs.append(paraphrased)
            except Exception as e:
                LOG.warning("paraphrase generation failed: %s", str(e))
    LOG.info("paraphrase: generated=%d kept=%d", attempted, len(outs))
    return outs
