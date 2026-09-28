import os

import pytest

from app.config import Settings
from app.llm.client import StructuredLLM
from app.rerank.rerankers import CrossEncoderReranker, LLMReranker, PassthroughReranker, get_reranker
from app.schemas import Candidate
from app.seed_data import load_startups
from tests.fakes import ScriptedBackend

STARTUPS = {s.id: s for s in load_startups()}


def candidates(*ids_and_scores):
    return [Candidate(startup=STARTUPS[i], vector_score=score) for i, score in ids_and_scores]


def test_passthrough_orders_by_vector_score():
    ranked = PassthroughReranker().rerank("q", candidates(("s02", 0.3), ("s01", 0.9)))
    assert [c.startup.id for c in ranked] == ["s01", "s02"]
    assert ranked[0].rerank_score == 0.9


def test_llm_reranker_uses_model_scores(tmp_path):
    backend = ScriptedBackend(['{"scores": [{"startup_id": "s21", "score": 3}, {"startup_id": "s01", "score": 9}]}'])
    llm = StructuredLLM(backend, Settings(demo_cache_dir=str(tmp_path)))
    ranked = LLMReranker(llm).rerank("bayi şikayetleri", candidates(("s21", 0.9), ("s01", 0.5)))
    assert [c.startup.id for c in ranked] == ["s01", "s21"]
    assert ranked[0].rerank_score == pytest.approx(0.9)


def test_factory_selects_backend():
    assert get_reranker(Settings(rerank_backend="none")).name == "none"
    assert get_reranker(Settings(rerank_backend="cross_encoder")).name == "cross_encoder"


@pytest.mark.skipif(os.getenv("NEEDLE_REAL_MODELS") != "1", reason="Gerçek model testi: NEEDLE_REAL_MODELS=1")
def test_multilingual_cross_encoder_prefers_the_safety_startup():
    reranker = CrossEncoderReranker("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
    ranked = reranker.rerank(
        "Şantiyelerde baret ve yelek kullanımını denetlemek zor, kazalar oluyor.",
        candidates(("s26", 0.41), ("s07", 0.39), ("s08", 0.38)),
    )
    assert ranked[0].startup.id == "s08"
    assert 0.0 <= ranked[-1].rerank_score <= 1.0
