import json, os, time, pathlib, logging
from typing import Any, Dict, Optional

LOG = logging.getLogger("synth.debug")

class JsonlSink:
    def __init__(self, path: str, flush_every: int = 50):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.flush_every = flush_every
        self._f = self.path.open("a", encoding="utf-8")
        self._n = 0

    def write(self, obj: Dict[str, Any]):
        self._f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._n += 1
        if self._n % self.flush_every == 0:
            self._f.flush()
            os.fsync(self._f.fileno())

    def close(self):
        try:
            self._f.flush()
            os.fsync(self._f.fileno())
        finally:
            self._f.close()

def setup_logging(level_str: str = "INFO"):
    level = getattr(logging, level_str.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # silence very noisy libs at INFO
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
