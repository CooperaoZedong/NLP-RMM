import os, json, time, random, logging
from typing import Optional
import boto3
LOG = logging.getLogger("synth.provider.bedrock")

class BedrockClient:
    def __init__(self, model: str, region: Optional[str] = None, max_tokens: int = 1200):
        self.br = boto3.client("bedrock-runtime", region_name=region or os.getenv("AWS_REGION","us-east-1"))
        self.model = model
        self.max_tokens = max_tokens

    def chat(self, system: str, user: str, temperature: float, top_p: float) -> str:
        rsp = self.br.converse(
            modelId=self.model, 
            system=[{"text": system}],
            messages=[{"role":"user","content":[{"text":user}]}],
            inferenceConfig={
                "maxTokens": self.max_tokens,
                "temperature": temperature,
                "topP": top_p 
            }
        )
        out = rsp["output"]["message"]
        LOG.debug("bedrock ok len=%s", "".join([c["text"] for c in out["content"]]))
        return "".join([c["text"] for c in out["content"]])
