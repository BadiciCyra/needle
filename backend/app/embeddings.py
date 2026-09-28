"""Metin → vektör katmanı. Varsayılan: yerel, çok dilli, açık kaynak sentence-transformers modeli."""

import hashlib
import math
from functools import lru_cache
from typing import Protocol

from app.config import get_settings


class Embedder(Protocol):
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    """Model ilk kullanımda yüklenir; vektörler normalize edilir (kosinüs = iç çarpım)."""

    def __init__(self, model_name: str, dim: int):
        self.model_name = model_name
        self.dim = dim
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class HashingEmbedder:
    """Model gerektirmeyen, deterministik sahte embedder (testler için).

    Kelimeleri sabit boyutlu bir vektöre hash'ler; ortak kelimesi çok olan metinler birbirine yakın düşer.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in text.lower().split():
            index = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dim
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    return SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_dim)
