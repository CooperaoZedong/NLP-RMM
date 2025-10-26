from typing import List, Protocol
import logging

from synth.prompts import SYSTEM_PARAPHRASE, USER_PARAPHRASE_TMPL
from synth.utils.json_utils import norm_text

LOG = logging.getLogger("synth.paraphrase")

class LLMClient(Protocol):
    def chat(self, system: str, user: str, temperature: float, top_p: float) -> str: ...

def paraphrases(client: LLMClient, seed_text: str, k: int, temperature: float, top_p: float) -> List[str]:
    outs, seen = [], set()
    attempted = 0
    for _ in range(k):
        attempted += 1
        user = USER_PARAPHRASE_TMPL.format(seed_text=seed_text)
        txt = client.chat(SYSTEM_PARAPHRASE, user, temperature=temperature, top_p=top_p).strip().strip('"')
        if len(txt) <= 15:
            LOG.debug("paraphrase too short: %r", txt)
            continue
        nx = norm_text(txt)
        if nx in seen:
            LOG.debug("paraphrase duplicate: %r", txt)
            continue
        outs.append(txt); seen.add(nx)
    LOG.info("paraphrase: generated=%d kept=%d", attempted, len(outs))
    return outs
