"""FastAPI bağımlılıkları. Testlerde app.dependency_overrides ile sahteleri takılabilir."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.embeddings import Embedder, get_embedder
from app.llm.client import StructuredLLM, get_structured_llm
from app.rerank.rerankers import Reranker, get_reranker
from app.retrieval.base import Retriever
from app.retrieval.pgvector import PgVectorRetriever


def llm_dep() -> StructuredLLM:
    return get_structured_llm()


def embedder_dep() -> Embedder:
    return get_embedder()


def reranker_dep(settings: Settings = Depends(get_settings), llm: StructuredLLM = Depends(llm_dep)) -> Reranker:
    return get_reranker(settings, llm)


def retriever_dep(session: Session = Depends(get_db)) -> Retriever:
    return PgVectorRetriever(session)
