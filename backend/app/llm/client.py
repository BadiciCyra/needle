"""Sağlayıcıdan bağımsız LLM katmanı.

Herhangi bir OpenAI uyumlu uç noktayla konuşur (OmniRoute, Ollama, doğrudan sağlayıcı).
Yapılandırılmış çıktı için sağlayıcıların tool-calling / JSON-schema desteğine güvenmez:
modelden JSON ister, Pydantic ile doğrular, uymazsa hatayı modele geri verip yeniden dener.
"""

import json
import re
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.llm.cache import DemoCache, DemoCacheMiss

T = TypeVar("T", bound=BaseModel)


class LLMBackend(Protocol):
    """Mesaj listesini alıp düz metin cevap döndüren her şey (gerçek model ya da test sahtesi)."""

    model_name: str

    def complete(self, messages: list[dict]) -> str: ...


class LLMNotConfigured(RuntimeError):
    """LLM_API_KEY tanımlı değil."""


class OpenAICompatibleBackend:
    """langchain-openai üzerinden herhangi bir OpenAI uyumlu uç noktaya bağlanır."""

    def __init__(self, settings: Settings):
        from langchain_openai import ChatOpenAI

        if not settings.llm_api_key:
            raise LLMNotConfigured("LLM_API_KEY boş")

        self.model_name = settings.llm_model
        self._chat = ChatOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            timeout=90,
            max_retries=1,
        )

    def complete(self, messages: list[dict]) -> str:
        result = self._chat.invoke([(m["role"], m["content"]) for m in messages])
        return result.content if isinstance(result.content, str) else str(result.content)


class StructuredOutputError(RuntimeError):
    """Model tüm denemelerde şemaya uygun JSON üretemedi."""


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> str:
    """Cevaptan JSON gövdesini çıkarır (```json bloklarını ve baştaki/sondaki metni temizler)."""
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if start == -1:
        raise ValueError("Cevapta JSON bulunamadı")
    end = max(text.rfind("}"), text.rfind("]"))
    return text[start : end + 1]


def _schema_instruction(schema: type[BaseModel]) -> str:
    return (
        "Cevabını SADECE aşağıdaki JSON şemasına uyan tek bir JSON nesnesi olarak ver. "
        "Açıklama, markdown veya ek metin yazma. Metinde olmayan bilgiyi uydurma; bilinmeyen alanlar null olsun.\n"
        f"JSON şeması:\n{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
    )


class StructuredLLM:
    """Şemaya uygun çıktı üreten, yeniden deneyen ve demo önbelleğini yöneten sarmalayıcı."""

    def __init__(self, backend: LLMBackend, settings: Settings | None = None):
        self.backend = backend
        self.settings = settings or get_settings()
        self.cache = DemoCache(self.settings.demo_cache_dir)

    def invoke(self, schema: type[T], system: str, user: str) -> T:
        messages = [
            {"role": "system", "content": f"{system}\n\n{_schema_instruction(schema)}"},
            {"role": "user", "content": user},
        ]
        key = DemoCache.key(self.backend.model_name, schema.__name__, messages)
        mode = self.settings.demo_mode

        if mode in ("record", "replay"):
            cached = self.cache.get(key)
            if cached is not None:
                return schema.model_validate_json(extract_json(cached))
            if mode == "replay":
                raise DemoCacheMiss(f"Önbellekte yok: {schema.__name__} ({key})")

        last_error: Exception | None = None
        for _ in range(self.settings.llm_max_retries + 1):
            raw = self.backend.complete(messages)
            try:
                parsed = schema.model_validate_json(extract_json(raw))
            except (ValueError, ValidationError) as error:
                last_error = error
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": f"Cevabın şemaya uymadı: {error}. Sadece geçerli JSON ile tekrar cevap ver.",
                    },
                ]
                continue
            if mode == "record":
                self.cache.put(key, raw, meta={"schema": schema.__name__, "model": self.backend.model_name})
            return parsed

        raise StructuredOutputError(f"{schema.__name__} için geçerli JSON alınamadı: {last_error}")


def get_structured_llm() -> StructuredLLM:
    settings = get_settings()
    return StructuredLLM(OpenAICompatibleBackend(settings), settings)
