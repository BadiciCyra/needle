"""Uçtan uca API testi: gerçek Postgres + pgvector, sahte LLM.

Çalıştırmak için (docker compose up -d db sonrası):
    NEEDLE_TEST_DATABASE_URL=postgresql+psycopg://needle:needle@127.0.0.1:5432/needle python -m pytest tests/test_api_integration.py
"""

import os

import pytest

DB_URL = os.getenv("NEEDLE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="Entegrasyon testi: NEEDLE_TEST_DATABASE_URL gerekli")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.api import deps
    from app.config import Settings, get_settings
    from app.db import session as db_session
    from app.db.models import Base, Startup
    from app.embeddings import HashingEmbedder
    from app.llm.client import StructuredLLM
    from app.main import app
    from app.rerank.rerankers import PassthroughReranker
    from app.seed_data import load_startups
    from tests.test_brief_graph import COMPLETE_BRIEF, PARTIAL_BRIEF, QUESTIONS
    from tests.test_match_graph import EchoRationaleBackend

    get_settings.cache_clear()
    db_session.get_engine.cache_clear()
    engine = db_session.get_engine()
    Base.metadata.drop_all(engine)
    db_session.init_db(engine)

    embedder = HashingEmbedder()
    with db_session.get_session_factory()() as s:
        for p, vector in zip(load_startups(), embedder.embed_documents([p.to_search_text() for p in load_startups()])):
            s.add(Startup(
                id=p.id, name=p.name, sector=p.sector, maturity=p.maturity.value, location=p.location,
                capabilities=p.capabilities, description=p.description, past_pilots=p.past_pilots, embedding=vector,
            ))
        s.commit()

    settings = Settings(database_url=DB_URL, demo_cache_dir=str(tmp_path))

    class RoutingBackend:
        """Brief çağrılarına sırayla yazılı cevap, gerekçe çağrısına EchoRationaleBackend."""

        model_name = "fake-model"

        def __init__(self):
            self.brief_responses = [PARTIAL_BRIEF, QUESTIONS, COMPLETE_BRIEF]
            self.rationale = EchoRationaleBackend()

        def complete(self, messages):
            if "Kısa liste (matches)" in messages[1]["content"]:
                return self.rationale.complete(messages)
            return self.brief_responses.pop(0)

    llm = StructuredLLM(RoutingBackend(), settings)
    app.dependency_overrides[deps.llm_dep] = lambda: llm
    app.dependency_overrides[deps.embedder_dep] = lambda: embedder
    app.dependency_overrides[deps.reranker_dep] = lambda: PassthroughReranker()
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))


def test_full_flow_need_to_pilot(client):
    need = client.post("/needs", json={
        "raw_text": "Sahadaki bayilerimizden gelen şikayetleri daha hızlı sınıflandırmak istiyoruz, çok manuel gidiyor.",
        "organization": {"name": "Kuzey Beyaz Eşya", "author_unit": "İnovasyon", "owner_unit": "Bayi Satış"},
    })
    assert need.status_code == 200, need.text
    body = need.json()
    assert body["status"] == "needs_input"
    assert {q["field"] for q in body["questions"]} == {"scope", "success_criteria", "timeline"}

    # Brief tamamlanmadan eşleştirme yapılamaz
    assert client.post(f"/briefs/{body['brief_id']}/match").status_code == 409

    answered = client.post(f"/briefs/{body['brief_id']}/answers", json={"answers": {
        "scope": "Ayda 3.000 şikayet", "success_criteria": "%85 doğruluk", "timeline": "3 ay",
    }})
    assert answered.status_code == 200, answered.text
    assert answered.json()["status"] == "final"

    match = client.post(f"/briefs/{body['brief_id']}/match")
    assert match.status_code == 200, match.text
    result = match.json()
    assert len(result["shortlist"]) == 5 and len(result["rejected"]) == 3
    assert result["shortlist"][0]["startup"]["id"] == "s01"
    assert result["retrieval_trace"]

    top_match_id = result["match_ids"]["s01"]
    decision = client.post(f"/matches/{top_match_id}/decision", json={"decision": "accept"})
    assert decision.status_code == 200
    assert decision.json()["pilot_id"] is not None

    again = client.post(f"/matches/{top_match_id}/decision", json={"decision": "decline"})
    assert again.status_code == 409

    assert len(client.get("/startups").json()) == 40
