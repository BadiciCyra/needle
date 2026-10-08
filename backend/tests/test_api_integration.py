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


def register(client, email: str, organization: str | None = None, account_type: str = "firma"):
    response = client.post("/auth/register", json={
        "name": "Deneme Kullanıcı", "email": email, "password": "uzun-bir-sifre-123",
        "organization_name": organization, "account_type": account_type, "kvkk_onay": True,
    })
    assert response.status_code == 200, response.text
    return response.json()


def admin_client():
    from fastapi.testclient import TestClient

    from app.auth import hash_password
    from app.db import session as db_session
    from app.db.models import User
    from app.main import app

    with db_session.get_session_factory()() as s:
        if not s.query(User).filter_by(email="yonetici@program.example").first():
            s.add(User(email="yonetici@program.example", password_hash=hash_password("yonetici-sifresi-1"),
                       name="Program Yöneticisi", role="yonetici"))
            s.commit()
    admin = TestClient(app)
    assert admin.post("/auth/login", json={"email": "yonetici@program.example", "password": "yonetici-sifresi-1"}).status_code == 200
    return admin


def matched_need(client) -> tuple[int, dict]:
    """Firma oturumunda tamamlanmış brief + eşleştirme sonucu."""
    body = client.post("/needs", json={
        "raw_text": "Sahadaki bayilerimizden gelen şikayetleri daha hızlı sınıflandırmak istiyoruz, çok manuel gidiyor.",
    }).json()
    client.post(f"/briefs/{body['brief_id']}/answers", json={"answers": {
        "scope": "Ayda 3.000 şikayet", "success_criteria": "%85 doğruluk", "timeline": "3 ay",
    }})
    return body["brief_id"], client.post(f"/briefs/{body['brief_id']}/match").json()


def set_website(startup_id: str, url: str):
    from app.db import session as db_session
    from app.db.models import Startup

    with db_session.get_session_factory()() as s:
        s.get(Startup, startup_id).website = url
        s.commit()


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
    decision = client.post(f"/matches/{top_match_id}/decision", json={"decision": "accept", "note": "Görüşelim"})
    assert decision.status_code == 200
    # Kabul pilotu değil tanıştırmayı başlatır; girişimin hesabı yok, yönetici onun adına cevaplar
    intro_id = decision.json()["introduction_id"]
    assert client.get("/pilots").json() == []
    [intro] = client.get("/introductions").json()
    assert intro["status"] == "bekliyor" and intro["firm_note"] == "Görüşelim" and not intro["startup_has_account"]
    assert client.post(f"/introductions/{intro_id}/respond", json={"decision": "kabul"}).status_code == 403
    answered = admin_client().post(f"/introductions/{intro_id}/respond", json={"decision": "kabul", "note": "Telefonla görüşüldü"})
    assert answered.status_code == 200 and answered.json()["responded_by"] == "yonetici"

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
    assert by_id[top_match_id]["introduction"]["status"] == "kabul"
    assert by_id[declined_id]["declined_reason"] == "Bütçe uymadı" and by_id[declined_id]["rejection"] is None

    pilot_id = answered.json()["pilot_id"]
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

    admin = admin_client()
    assert TestClient(app).post("/auth/login", json={"email": "yonetici@program.example", "password": "yanlis"}).status_code == 401
    assert TestClient(app).post("/auth/login", json={"email": "YONETICI@program.example", "password": "yonetici-sifresi-1"}).status_code == 200
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


def test_startup_claims_profile_and_answers_introduction(client):
    from fastapi.testclient import TestClient

    from app.main import app

    register(client, "inovasyon@kuzey.example", "Kuzey Beyaz Eşya")
    brief_id, result = matched_need(client)
    intro_id = client.post(f"/matches/{result['match_ids']['s01']}/decision", json={"decision": "accept"}).json()["introduction_id"]

    set_website("s01", "https://www.metinsel.example/tr")
    startup = TestClient(app)
    me = register(startup, "ali@metinsel.example", account_type="girisim")
    assert me["role"] == "girisim" and me["organization"] is None and me["startup"] is None

    # Girişim kurum kayıtlarını göremez (organization_id boş diye "kısıtsız" sayılmamalı)
    assert startup.get("/needs").status_code == 403
    assert startup.get(f"/briefs/{brief_id}").status_code == 403
    assert startup.get(f"/briefs/{brief_id}/match").status_code == 403
    assert startup.get("/introductions").status_code == 403  # profil doğrulanmadan davet yok

    # Şirket e-postası sitenin alan adıyla eşleşiyor → anında doğrulanır
    me = startup.post("/startup-account/claim", json={"startup_id": "s01"}).json()
    assert me["startup"] == {"id": "s01", "name": me["startup"]["name"], "status": "aktif", "verified": True}

    [intro] = startup.get("/introductions").json()
    assert intro["id"] == intro_id and intro["organization"] == "Kuzey Beyaz Eşya"
    assert intro["brief"]["required_capabilities"]
    answered = startup.post(f"/introductions/{intro_id}/respond", json={"decision": "kabul", "note": "Memnuniyetle"}).json()
    assert answered["status"] == "kabul" and answered["responded_by"] == "girisim"
    assert startup.post(f"/introductions/{intro_id}/respond", json={"decision": "ret"}).status_code == 409

    # İki taraf aynı pilotu görür; girişim kilometre taşı ekler ama sonucu kurum belirler
    [pilot] = startup.get("/pilots").json()
    assert pilot["id"] == answered["pilot_id"] and [p["id"] for p in client.get("/pilots").json()] == [pilot["id"]]
    assert startup.post(f"/pilots/{pilot['id']}/milestones", json={"title": "Örnek veri"}).status_code == 200
    assert startup.patch(f"/pilots/{pilot['id']}", json={"result": "evet"}).status_code == 403

    # Aynı profili ikinci bir hesap sahiplenemez
    other = TestClient(app)
    register(other, "veli@metinsel.example", account_type="girisim")
    assert other.post("/startup-account/claim", json={"startup_id": "s01"}).status_code == 409


def test_unverified_claim_and_new_profile_need_admin_approval(client):
    register(client, "kisisel@gmail.com", account_type="girisim")
    set_website("s02", "https://s02.example")
    me = client.post("/startup-account/claim", json={"startup_id": "s02"}).json()
    assert me["startup"]["verified"] is False  # kişisel e-posta: yönetici onayı gerekir

    from fastapi.testclient import TestClient

    from app.main import app

    newcomer = TestClient(app)
    register(newcomer, "kurucu@yeni-girisim.example", account_type="girisim")
    profile = {
        "name": "Yeni Girişim", "sector": "enerji", "maturity": "mvp", "location": "İzmir",
        "website": "https://yeni-girisim.example", "description": "Akustik sensörle su şebekesinde kaçak tespiti yapıyoruz.",
        "capabilities": ["akustik sensörle su kaçağı tespiti", "şebeke basınç izleme"],
    }
    me = newcomer.post("/startup-account/new", json=profile).json()
    assert me["startup"]["status"] == "onay_bekliyor"
    new_id = me["startup"]["id"]
    assert new_id not in {s["id"] for s in client.get("/startups").json()}  # onaysız profil havuzda görünmez

    admin = admin_client()
    claims = {c["kind"]: c for c in admin.get("/admin/claims").json()}
    assert claims["sahiplenme"]["domain_match"] is False and claims["yeni_profil"]["startup"]["id"] == new_id
    assert admin.post(f"/admin/claims/{claims['yeni_profil']['user_id']}/approve").status_code == 204
    assert admin.post(f"/admin/claims/{claims['sahiplenme']['user_id']}/reject").status_code == 204

    assert newcomer.get("/auth/me").json()["startup"] == {"id": new_id, "name": "Yeni Girişim", "status": "aktif", "verified": True}
    assert new_id in {s["id"] for s in admin.get("/startups").json()}
    assert client.get("/auth/me").json()["startup"] is None  # reddedilen sahiplenme: başka profil deneyebilir
    assert client.get("/startup-account/profile").status_code == 404


def test_open_call_application_becomes_pilot(client):
    from fastapi.testclient import TestClient

    from app.main import app

    register(client, "inovasyon@kuzey.example", "Kuzey Beyaz Eşya")
    brief_id, _ = matched_need(client)
    call = client.post("/calls", json={
        "brief_id": brief_id, "title": "Bayi şikayetlerini sınıflandıracak girişim arıyoruz",
        "summary": "Ayda 3.000 Türkçe şikayet metnini %85 doğrulukla otomatik sınıflandırmak istiyoruz.",
        "hide_organization": True,
    })
    assert call.status_code == 200, call.text
    call_id = call.json()["id"]
    assert client.post("/calls", json={**call.json(), "brief_id": brief_id}).status_code == 409
    assert client.get(f"/briefs/{brief_id}/match").json()["open_call_id"] == call_id

    set_website("s03", "https://s03.example")
    startup = TestClient(app)
    register(startup, "ekip@s03.example", account_type="girisim")
    startup.post("/startup-account/claim", json={"startup_id": "s03"})
    [listed] = startup.get("/calls").json()
    assert listed["organization"] is None and listed["application_count"] == 0  # kurum adı gizli
    note = {"note": "Türkçe şikayet metinlerini sınıflandıran hazır modelimiz var, iki haftada kurarız."}
    applied = startup.post(f"/calls/{call_id}/applications", json=note).json()
    assert applied["my_application"]["status"] == "yeni"
    assert startup.post(f"/calls/{call_id}/applications", json=note).status_code == 409

    # Başka bir firma çağrıyı göremez
    other = TestClient(app)
    register(other, "b@firma-b.example", "Firma B")
    assert other.get("/calls").json() == [] and other.get(f"/calls/{call_id}").status_code == 404

    detail = client.get(f"/calls/{call_id}").json()
    assert detail["organization"] == "Kuzey Beyaz Eşya" and detail["application_count"] == 1
    [app_] = detail["applications"]
    assert startup.post(f"/applications/{app_['id']}/decision", json={"decision": "kabul"}).status_code == 403
    decided = client.post(f"/applications/{app_['id']}/decision", json={"decision": "kabul", "note": "Başlayalım"}).json()
    assert decided["applications"][0]["status"] == "kabul" and decided["applications"][0]["pilot_id"]

    [pilot] = startup.get("/pilots").json()
    assert pilot["startup"]["id"] == "s03" and pilot["match_id"] is None
    [intro] = startup.get("/introductions").json()
    assert intro["source"] == "cagri" and intro["status"] == "kabul"

    assert client.patch(f"/calls/{call_id}", json={"status": "kapali"}).json()["status"] == "kapali"
    # Kapalı çağrı yeni girişimlere görünmez, başvuran yine görür
    assert [c["id"] for c in startup.get("/calls").json()] == [call_id]
