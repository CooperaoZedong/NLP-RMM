import os
from typing import Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

class OpenAIClient:
    def __init__(self, model: str, max_tokens: int = 1200, api_key: Optional[str] = None):
        if OpenAI is None:
            raise ImportError("openai package not installed. `pip install openai`")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.max_tokens = max_tokens

    def chat(self, system: str, user: str, temperature: float, top_p: float) -> str:
        rsp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role":"system","content":system},
                      {"role":"user","content":user}],
            temperature=temperature,
            top_p=top_p,
            max_tokens=self.max_tokens
        )
        return rsp.choices[0].message.content
