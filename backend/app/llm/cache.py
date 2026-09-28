"""Demo önbelleği: LLM cevaplarını diske yazar ve gerektiğinde tekrar oynatır.

Sahnede internet ya da sağlayıcı çökerse `DEMO_MODE=replay` ile aynı akış önbellekten çalışır.
"""

import hashlib
import json
from pathlib import Path


class DemoCacheMiss(RuntimeError):
    """replay modunda önbellekte olmayan bir istek geldi."""


class DemoCache:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    @staticmethod
    def key(model: str, schema_name: str, messages: list[dict]) -> str:
        payload = json.dumps(
            {"model": model, "schema": schema_name, "messages": messages},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> str | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["response"]

    def put(self, key: str, response: str, meta: dict | None = None) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        record = {"response": response, "meta": meta or {}}
        self._path(key).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
