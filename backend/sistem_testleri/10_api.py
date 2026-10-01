"""SİSTEM 10 — API uçtan uca (app/api/routes.py, app/main.py)

Gerçek Postgres + pgvector, gerçek embedding ve reranker ile tüm akışı HTTP istekleriyle yürütür.
LLM varsayılan olarak sahtedir; --gercek ile OmniRoute kullanılır.

Veritabanını SİLMEZ: sadece bu script'in oluşturduğu satırları sonunda temizler
(saklamak için --birak ekle).

Ne gösterir (her isteğin kodu ve cevabın özeti):
  1. GET  /health
  2. GET  /startups
  3. POST /needs                       → takip soruları
  4. POST /briefs/{id}/match (erken)    → 409
  5. POST /briefs/{id}/answers          → brief final
  6. POST /briefs/{id}/match            → 5 + 3 sonuç, RAG kaydı
  7. POST /matches/{id}/decision accept → pilot kartı
  8. POST /matches/{id}/decision (tekrar) → 409
  9. POST /matches/{id}/decision decline + sebep
 10. Veritabanında oluşan satırlar

Gerekli:  docker compose up -d db   ve   python -m seed.seed_db (bir kez)
Çalıştırma:  python sistem_testleri/10_api.py [--gercek] [--birak]
"""

import json
import sys
import tempfile
import time

from _ortak import adim, baslik, bilgi, bitir, gercek_mod, kontrol, ozetle

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api import deps
from app.config import Settings, get_settings
from app.db.session import get_engine
from app.llm.client import StructuredLLM
from app.main import app

HAM = "Sahadaki bayilerimizden gelen şikayetleri daha hızlı sınıflandırmak istiyoruz, çok manuel gidiyor."
EKSIK = json.dumps({"title": "Bayi şikayetlerinin sınıflandırılması",
                    "problem": "Bayi şikayetleri elle sınıflandırılıyor",
                    "required_capabilities": ["Türkçe metin sınıflandırma", "şikayet ve talep kategorizasyonu"]},
                   ensure_ascii=False)
SORULAR = json.dumps({"questions": [
    {"field": "scope", "question": "Ayda kaç şikayet geliyor?"},
    {"field": "success_criteria", "question": "Başarı ölçütünüz nedir?"},
    {"field": "timeline", "question": "Pilot ne kadar sürmeli?"}]}, ensure_ascii=False)
TAM = json.dumps({"title": "Bayi şikayetlerinin sınıflandırılması", "problem": "Bayi şikayetleri elle sınıflandırılıyor",
                  "scope": "Ayda 3.000 şikayet", "success_criteria": "%85 doğruluk", "timeline": "3 ay",
                  "required_capabilities": ["Türkçe metin sınıflandırma", "şikayet ve talep kategorizasyonu"]},
                 ensure_ascii=False)


class YonlendirenSahteLLM:
    """Brief çağrılarına sırayla yazılı cevap, gerekçe çağrısına aday id'lerinden üretilmiş gerekçe."""

    model_name = "sahte-model"

    def __init__(self):
        self.brief = [EKSIK, SORULAR, TAM]

    def complete(self, messages):
        user = messages[1]["content"]
        if "Kısa liste (matches)" not in user:
            return self.brief.pop(0)
        kisa, elenen = user.split("Elenenler (rejections):")
        ids = lambda m: [s[1:4] for s in m.splitlines() if s.startswith("[s")]
        return json.dumps({
            "matches": [{"startup_id": i, "fit_summary": "Uygun.", "evidence": []} for i in ids(kisa)],
            "rejections": [{"startup_id": i, "near_miss_reason": "Yakındı ama yetkinlik eksik."} for i in ids(elenen)],
        }, ensure_ascii=False)


def istek(istemci, yontem, yol, **kw):
    t = time.perf_counter()
    cevap = getattr(istemci, yontem)(yol, **kw)
    bilgi(f"{yontem.upper():<5} {yol:<32} → {cevap.status_code}  ({time.perf_counter() - t:.1f} sn)")
    return cevap


baslik("SİSTEM 10 — API UÇTAN UCA")
try:
    with get_engine().connect() as conn:
        girisim = conn.execute(text("select count(embedding) from startups")).scalar()
except Exception as hata:
    kontrol(False, f"veritabanına bağlanılamadı → 'docker compose up -d db' ({type(hata).__name__})")
    bitir()
if not kontrol(girisim == 40, f"veritabanında embedding'li 40 girişim var ({girisim})"):
    bilgi("→ önce 'python -m seed.seed_db' çalıştır")
    bitir()

if not gercek_mod():
    sahte_llm = StructuredLLM(YonlendirenSahteLLM(), Settings(demo_mode="off", demo_cache_dir=tempfile.mkdtemp()))
    app.dependency_overrides[deps.llm_dep] = lambda: sahte_llm
    bilgi("LLM: sahte (gerçek için --gercek)")
else:
    bilgi(f"LLM: GERÇEK ({get_settings().llm_model})")
istemci = TestClient(app)
olusan = {}

adim(1, "Sağlık kontrolü")
saglik = istek(istemci, "get", "/health").json()
bilgi(json.dumps(saglik, ensure_ascii=False), girinti=8)
kontrol(saglik["status"] == "ok", "API ayakta")

adim(2, "Girişim havuzu")
liste = istek(istemci, "get", "/startups").json()
kontrol(len(liste) == 40, "40 girişim döndü")

adim(3, "İhtiyaç gönder")
c = istek(istemci, "post", "/needs", json={"raw_text": HAM, "organization": {
    "name": "Sistem Testi A.Ş.", "author_unit": "İnovasyon", "owner_unit": "Bayi Satış"}})
govde = c.json()
olusan.update(brief=govde.get("brief_id"), need=govde.get("need_id"))
bilgi(f"brief_id={govde.get('brief_id')}  durum={govde.get('status')}", girinti=8)
for q in govde.get("questions", []):
    bilgi(f"[{q['field']}] {q['question']}", girinti=8)
kontrol(c.status_code == 200, "ihtiyaç kabul edildi")
brief_id = govde["brief_id"]

if govde["status"] == "needs_input":
    adim(4, "Brief tamamlanmadan eşleştirme denemesi")
    erken = istek(istemci, "post", f"/briefs/{brief_id}/match")
    bilgi(erken.json()["detail"], girinti=8)
    kontrol(erken.status_code == 409, "409: önce takip soruları cevaplanmalı")

    adim(5, "Takip sorularını cevapla")
    cevaplar = {q["field"]: {"scope": "Ayda yaklaşık 3.000 şikayet", "success_criteria": "%85 doğru kategori",
                             "timeline": "3 aylık pilot"}.get(q["field"], "Bilmiyoruz")
                for q in govde["questions"]}
    c = istek(istemci, "post", f"/briefs/{brief_id}/answers", json={"answers": cevaplar})
    kontrol(c.status_code == 200 and c.json()["status"] == "final", "brief tamamlandı (final)")

adim(6, "Eşleştir")
c = istek(istemci, "post", f"/briefs/{brief_id}/match")
sonuc = c.json()
olusan["run"] = sonuc.get("run_id")
for satir in sonuc.get("retrieval_trace", []):
    bilgi(satir, girinti=8)
for k in sonuc.get("shortlist", []):
    bilgi(f"{k['rank']}. {k['startup']['name']:<16} {k['score']:.3f}  {ozetle(k['rationale']['fit_summary'], 70)}", girinti=8)
for k in sonuc.get("rejected", []):
    bilgi(f"✗ {k['startup']['name']:<16} {k['score']:.3f}  {ozetle(k['rejection']['near_miss_reason'], 70)}", girinti=8)
kontrol(c.status_code == 200, "eşleştirme başarılı")
kontrol(len(sonuc["shortlist"]) == 5 and len(sonuc["rejected"]) == 3, "5 + 3 sonuç")
kontrol(len(sonuc["match_ids"]) == 8, "8 eşleşme kaydı oluştu ve id'leri döndü")
kontrol(sonuc["shortlist"][0]["startup"]["name"] == "Metinsel", "1. sırada Metinsel")

adim(7, "Birinci adayı kabul et → pilot kartı")
ilk_id = sonuc["match_ids"][sonuc["shortlist"][0]["startup"]["id"]]
c = istek(istemci, "post", f"/matches/{ilk_id}/decision", json={"decision": "accept"})
olusan["pilot"] = c.json().get("pilot_id")
bilgi(json.dumps(c.json(), ensure_ascii=False), girinti=8)
kontrol(c.json()["status"] == "accepted" and c.json()["pilot_id"], "kabul edildi, pilot kartı açıldı")

adim(8, "Aynı eşleşmeye ikinci karar")
c = istek(istemci, "post", f"/matches/{ilk_id}/decision", json={"decision": "decline"})
kontrol(c.status_code == 409, "409: karar bir kez verilir")

adim(9, "İkinci adayı reddet + sebep (negatif eşleşme kaydı)")
ikinci_id = sonuc["match_ids"][sonuc["shortlist"][1]["startup"]["id"]]
c = istek(istemci, "post", f"/matches/{ikinci_id}/decision",
          json={"decision": "decline", "reason": "Bayi kanalı deneyimi yok"})
kontrol(c.json()["status"] == "declined", "reddedildi")

adim(10, "Veritabanında oluşan satırlar")
with get_engine().connect() as conn:
    for tablo, kosul in [("needs", f"id = {olusan['need']}"), ("briefs", f"id = {brief_id}"),
                         ("match_runs", f"brief_id = {brief_id}"), ("matches", f"brief_id = {brief_id}"),
                         ("pilots", f"id = {olusan['pilot']}")]:
        bilgi(f"{tablo:<11} {conn.execute(text(f'select count(*) from {tablo} where {kosul}')).scalar()} satır", girinti=8)
    red = conn.execute(text(f"select rejection->>'declined_reason' from matches where id = {ikinci_id}")).scalar()
kontrol(red == "Bayi kanalı deneyimi yok", "ret sebebi eşleşme kaydına yazıldı")

if "--birak" in sys.argv:
    bilgi("\n--birak: oluşturulan satırlar veritabanında bırakıldı")
else:
    with get_engine().begin() as conn:
        conn.execute(text(f"delete from pilots where id = {olusan['pilot']}"))
        conn.execute(text(f"delete from matches where brief_id = {brief_id}"))
        conn.execute(text(f"delete from match_runs where brief_id = {brief_id}"))
        org = conn.execute(text(f"select organization_id from needs where id = {olusan['need']}")).scalar()
        conn.execute(text(f"delete from briefs where id = {brief_id}"))
        conn.execute(text(f"delete from needs where id = {olusan['need']}"))
        if org:
            conn.execute(text(f"delete from organizations where id = {org}"))
    bilgi("\nbu script'in oluşturduğu satırlar temizlendi (girişimlere dokunulmadı)")

app.dependency_overrides.clear()
bitir()
