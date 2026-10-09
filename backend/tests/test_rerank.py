import json
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


def check(startup_id, nesne=True, is_=True, uyarlama=False):
    return {"startup_id": startup_id, "urun_ne_yapar": "x", "ayni_nesne": nesne, "ayni_is": is_, "uyarlama_gerekir": uyarlama}


def checks(*items):
    return json.dumps({"ihtiyac_nesnesi": "bayi şikayetleri", "istenen_is": "sınıflandırma", "adaylar": list(items)})


def llm_reranker(tmp_path, *responses, votes=1):
    llm = StructuredLLM(ScriptedBackend(list(responses)), Settings(demo_cache_dir=str(tmp_path)))
    return LLMReranker(llm, verify_top_n=8, votes=votes)


def test_llm_reranker_uses_model_scores(tmp_path):
    reranker = llm_reranker(
        tmp_path,
        '{"scores": [{"startup_id": "s21", "score": 3}, {"startup_id": "s01", "score": 9}]}',
        checks(check("s01")),
    )
    ranked = reranker.rerank("bayi şikayetleri", candidates(("s21", 0.9), ("s01", 0.5)))
    assert [c.startup.id for c in ranked] == ["s01", "s21"]
    assert ranked[0].rerank_score == pytest.approx(0.9)
    assert [c.direct_fit for c in ranked] == [True, False]
    assert "Denetlenmedi" in ranked[1].direct_fit_reason


def test_direct_fit_needs_all_three_answers(tmp_path):
    reranker = llm_reranker(
        tmp_path,
        '{"scores": [{"startup_id": "s01", "score": 9}, {"startup_id": "s21", "score": 8}, {"startup_id": "s02", "score": 8}]}',
        checks(check("s01"), check("s21", is_=False), check("s02", uyarlama=True)),
    )
    ranked = reranker.rerank("q", candidates(("s01", 0.5), ("s21", 0.5), ("s02", 0.5)))
    assert {c.startup.id: c.direct_fit for c in ranked} == {"s01": True, "s21": False, "s02": False}


def test_majority_vote_decides(tmp_path):
    scores = '{"scores": [{"startup_id": "s01", "score": 9}, {"startup_id": "s21", "score": 8}]}'
    reranker = llm_reranker(
        tmp_path,
        scores,
        checks(check("s01"), check("s21")),
        checks(check("s01"), check("s21", nesne=False)),
        checks(check("s01", uyarlama=True), check("s21", is_=False)),
        votes=3,
    )
    ranked = reranker.rerank("q", candidates(("s01", 0.5), ("s21", 0.5)))
    by_id = {c.startup.id: c for c in ranked}
    assert by_id["s01"].direct_fit and "2/3" in by_id["s01"].direct_fit_reason
    assert by_id["s21"].direct_fit is False and "1/3" in by_id["s21"].direct_fit_reason


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
