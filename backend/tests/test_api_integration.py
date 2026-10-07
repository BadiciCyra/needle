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


def register(client, email: str, organization: str):
    response = client.post("/auth/register", json={
        "name": "Deneme Kullanıcı", "email": email, "password": "uzun-bir-sifre-123",
        "organization_name": organization, "kvkk_onay": True,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_full_flow_need_to_pilot(client):
    assert client.get("/needs").status_code == 401  # oturum olmadan veri yok
    register(client, "inovasyon@kuzey.example", "Kuzey Beyaz Eşya")

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

    declined_id = result["match_ids"][result["shortlist"][1]["startup"]["id"]]
    client.post(f"/matches/{declined_id}/decision", json={"decision": "decline", "reason": "Bütçe uymadı"})

    needs = client.get("/needs").json()
    assert needs[0]["brief_id"] == body["brief_id"] and needs[0]["accepted_count"] == 1
    assert needs[0]["organization"] == "Kuzey Beyaz Eşya"  # firma kendi kurumu adına girer

    saved = client.get(f"/briefs/{body['brief_id']}/match").json()
    by_id = {item["match_id"]: item for item in saved["shortlist"]}
    assert by_id[top_match_id]["status"] == "accepted"
    assert by_id[declined_id]["declined_reason"] == "Bütçe uymadı" and by_id[declined_id]["rejection"] is None

    pilot_id = decision.json()["pilot_id"]
    pilot = client.post(f"/pilots/{pilot_id}/milestones", json={"title": "Veri erişimi", "due_date": "2026-11-01"}).json()
    assert pilot["startup"]["id"] == "s01" and pilot["stale"] is False
    pilot = client.post(f"/milestones/{pilot['milestones'][0]['id']}/complete").json()
    assert pilot["milestones"][0]["completed_at"]
    pilot = client.patch(f"/pilots/{pilot_id}", json={"status": "done", "result": "kismen"}).json()
    assert pilot["status"] == "done" and pilot["result"] == "kismen"
    assert [p["id"] for p in client.get("/pilots").json()] == [pilot_id]

    assert len(client.get("/startups").json()) == 40


def test_firms_only_see_their_own_records(client):
    from fastapi.testclient import TestClient

    from app.auth import hash_password
    from app.db import session as db_session
    from app.db.models import User
    from app.main import app

    register(client, "a@firma-a.example", "Firma A")
    created = client.post("/needs", json={"raw_text": "Sahadaki bayilerimizden gelen şikayetleri sınıflandırmak istiyoruz."})
    brief_id = created.json()["brief_id"]

    other = TestClient(app)
    register(other, "b@firma-b.example", "Firma B")
    assert other.get("/needs").json() == []
    assert other.get(f"/briefs/{brief_id}").status_code == 404  # 403 değil: kaydın varlığı da sızmaz
    assert other.post(f"/briefs/{brief_id}/answers", json={"answers": {"scope": "x"}}).status_code == 404
    assert other.post(f"/briefs/{brief_id}/match").status_code == 404
    assert other.get("/pilots").json() == []

    with db_session.get_session_factory()() as s:
        s.add(User(email="yonetici@program.example", password_hash=hash_password("yonetici-sifresi-1"),
                   name="Program Yöneticisi", role="yonetici"))
        s.commit()
    admin = TestClient(app)
    assert admin.post("/auth/login", json={"email": "yonetici@program.example", "password": "yanlis-sifre"}).status_code == 401
    assert admin.post("/auth/login", json={"email": "YONETICI@program.example", "password": "yonetici-sifresi-1"}).status_code == 200
    assert [n["brief_id"] for n in admin.get("/needs").json()] == [brief_id]
    assert admin.get(f"/briefs/{brief_id}").status_code == 200

    assert other.post("/auth/logout").status_code == 204
    assert other.get("/needs").status_code == 401


def test_register_rejects_duplicates_and_missing_consent(client):
    register(client, "tek@firma.example", "Firma")
    duplicate = client.post("/auth/register", json={
        "name": "Başka", "email": "TEK@firma.example", "password": "uzun-bir-sifre-123",
        "organization_name": "Başka Firma", "kvkk_onay": True,
    })
    assert duplicate.status_code == 409
    no_consent = client.post("/auth/register", json={
        "name": "Başka", "email": "yeni@firma.example", "password": "uzun-bir-sifre-123",
        "organization_name": "Başka Firma", "kvkk_onay": False,
    })
    assert no_consent.status_code == 422


def test_profile_fills_empty_brief_fields(client):
    register(client, "profil@firma.example", "Profil Firma")
    me = client.put("/auth/profile", json={
        "sector": "perakende", "city": "İstanbul", "employee_range": "250-999", "systems": ["SAP"],
        "preferred_maturity": "mvp", "startup_location": "ayni_sehir", "pilot_duration": "3 ay",
    }).json()
    assert me["organization"]["onboarded"] is True

    body = client.post("/needs", json={"raw_text": "Sahadaki bayilerimizden gelen şikayetleri sınıflandırmak istiyoruz."}).json()
    brief = body["brief"]
    assert brief["sector"] == "perakende"
    assert brief["location_preference"] == "İstanbul"
    assert brief["min_maturity"] == "mvp"
    assert brief["timeline"] == "3 ay"  # profilden geldi; artık sorulmuyor
    assert "timeline" not in {q["field"] for q in body["questions"]}
