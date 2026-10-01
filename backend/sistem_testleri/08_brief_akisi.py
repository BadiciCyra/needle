"""SİSTEM 8 — Brief akışı (app/graphs/brief_graph.py)

Grafı düğüm düğüm çalıştırır ve her düğümün state'e ne yazdığını gösterir.

Ne gösterir:
  1. Eksik metin: extract_brief → check_completeness → ask_followups (hangi düğümden geçti, ne yazdı)
  2. Modelin uydurduğu fazladan sorunun ayıklanması
  3. Cevaplarla ikinci çağrı: merge_answers → check_completeness → finalize
  4. Cevaplar yine boşsa ikinci tur soru sorulmaması (sonsuz döngü yok)
  5. (--gercek) Gerçek LLM ile n01 ihtiyacı uçtan uca

Çalıştırma:  python sistem_testleri/08_brief_akisi.py            (sahte model)
             python sistem_testleri/08_brief_akisi.py --gercek   (OmniRoute)
"""

import json
import tempfile
import time

from _ortak import SiraliSahteLLM, adim, baslik, bilgi, bitir, gercek_mod, kontrol, ozetle

from app.config import Settings
from app.graphs.brief_graph import build_brief_graph
from app.llm.client import StructuredLLM

HAM = "Sahadaki bayilerimizden gelen şikayetleri daha hızlı sınıflandırmak istiyoruz, çok manuel gidiyor."

EKSIK_BRIEF = json.dumps({
    "title": "Bayi şikayetlerinin otomatik sınıflandırılması",
    "problem": "Bayilerden gelen şikayetler elle sınıflandırılıyor ve yavaş",
    "scope": None, "success_criteria": None, "timeline": None,
    "required_capabilities": ["Türkçe metin sınıflandırma", "şikayet ve talep kategorizasyonu"],
    "missing_fields": [],  # model "eksik yok" diyor; kod bunu yok sayacak
}, ensure_ascii=False)
SORULAR = json.dumps({"questions": [
    {"field": "scope", "question": "Ayda kaç şikayet geliyor, hangi kanallardan?"},
    {"field": "success_criteria", "question": "Hangi doğrulukta başarılı sayarsınız?"},
    {"field": "timeline", "question": "Pilot 3 ay mı, 6 ay mı sürmeli?"},
    {"field": "budget", "question": "Bütçeniz nedir?"},  # eksik olmayan alan → ayıklanmalı
]}, ensure_ascii=False)
TAM_BRIEF = json.dumps({
    "title": "Bayi şikayetlerinin otomatik sınıflandırılması",
    "problem": "Bayilerden gelen şikayetler elle sınıflandırılıyor ve yavaş",
    "scope": "Ayda ~3.000 şikayet; bayi portalı ve e-posta",
    "required_capabilities": ["Türkçe metin sınıflandırma"],
    "success_criteria": "%85 doğru kategori", "timeline": "3 ay",
}, ensure_ascii=False)
CEVAPLAR = {"scope": "Ayda yaklaşık 3.000 şikayet, bayi portalı ve e-posta üzerinden",
            "success_criteria": "Şikayetlerin %85'i doğru kategoriye düşmeli", "timeline": "3 aylık pilot",
            "problem": "Şikayetler elle okunup sınıflandırılıyor",
            "required_capabilities": "Türkçe metin sınıflandırma"}


def calistir(graf, girdi: dict) -> dict:
    """Grafı akış (stream) modunda çalıştırır: her düğümden sonra yazdığı güncellemeyi basar."""
    state = dict(girdi)
    for olay in graf.stream(girdi, stream_mode="updates"):
        for dugum, guncelleme in olay.items():
            anahtarlar = ", ".join(guncelleme) if guncelleme else "-"
            bilgi(f"→ {dugum:<20} yazdı: {anahtarlar}")
            state.update(guncelleme or {})
    return state


def sahte_graf(cevaplar: list[str]):
    sahte = SiraliSahteLLM(cevaplar)
    graf = build_brief_graph(StructuredLLM(sahte, Settings(demo_mode="off", demo_cache_dir=tempfile.mkdtemp())))
    return graf, sahte


baslik("SİSTEM 8 — BRIEF AKIŞI (LangGraph)")

adim(1, "Eksik metin → takip soruları")
bilgi(f"metin: \"{HAM}\"")
graf, sahte = sahte_graf([EKSIK_BRIEF, SORULAR])
sonuc = calistir(graf, {"raw_text": HAM})
bilgi(f"durum: {sonuc['status']}   eksik alanlar: {sonuc['missing_fields']}")
for soru in sonuc["questions"]:
    bilgi(f"[{soru['field']}] {soru['question']}", girinti=8)
kontrol(sonuc["status"] == "needs_input", "durum needs_input (kurumdan cevap bekleniyor)")
kontrol(sonuc["missing_fields"] == ["scope", "success_criteria", "timeline"],
        "model 'eksik yok' dese de kod 3 eksik alan buldu")
kontrol(len(sahte.cagrilar) == 2, "2 LLM çağrısı: brief çıkarma + soru üretme")

adim(2, "Modelin uydurduğu fazladan soru ayıklandı mı?")
kontrol("budget" not in [q["field"] for q in sonuc["questions"]], "eksik olmayan 'budget' için sorulan soru atıldı")

adim(3, "Kurum cevapladı → ikinci çağrı")
graf, sahte = sahte_graf([TAM_BRIEF])
girdi = {"raw_text": HAM, "answers": {k: CEVAPLAR[k] for k in ("scope", "success_criteria", "timeline")},
         "asked_questions": sonuc["questions"], "followup_rounds": 1}
sonuc2 = calistir(graf, girdi)
bilgi("modele giden mesajın cevaplar kısmı:")
bilgi(ozetle(sahte.cagrilar[0][1]["content"].split("takip sorularını")[1], 300), girinti=8)
kontrol(sonuc2["status"] == "final", "durum final")
kontrol(sonuc2["brief"]["timeline"] == "3 ay", "cevaplar brief'e girdi")
kontrol("Ayda yaklaşık 3.000 şikayet" in sahte.cagrilar[0][1]["content"], "cevaplar prompta eklendi")

adim(4, "Cevaplar yine boş → ikinci tur soru yok")
graf, sahte = sahte_graf([EKSIK_BRIEF])
sonuc3 = calistir(graf, {"raw_text": HAM, "answers": {"scope": "  "}, "asked_questions": [], "followup_rounds": 1})
kontrol(sonuc3["status"] == "final", "1 tur hakkı dolduğu için yeniden soru sorulmadı, akış bitti")
kontrol(sonuc3["brief"]["missing_fields"] == ["scope", "success_criteria", "timeline"],
        "brief eksikleri işaretlenmiş halde tamamlandı")

adim(5, "Gerçek LLM (--gercek)")
if not gercek_mod():
    bilgi("atlandı: gerçek modeli denemek için --gercek ekle")
else:
    from app.graphs.brief_graph import build_brief_graph as kur
    from app.llm.client import get_structured_llm

    graf = kur(get_structured_llm())
    t = time.perf_counter()
    ilk = calistir(graf, {"raw_text": HAM})
    bilgi(f"süre: {time.perf_counter() - t:.1f} sn   durum: {ilk['status']}")
    bilgi(json.dumps(ilk["brief"], ensure_ascii=False, indent=2), girinti=8)
    for soru in ilk.get("questions", []):
        bilgi(f"[{soru['field']}] {soru['question']}", girinti=8)
    kontrol(ilk["brief"].get("required_capabilities"), "gerçek model yetkinlik çıkardı")
    if ilk["status"] == "needs_input":
        cevap = {q["field"]: CEVAPLAR.get(q["field"], "Bilmiyoruz") for q in ilk["questions"]}
        t = time.perf_counter()
        son = calistir(graf, {"raw_text": HAM, "answers": cevap, "asked_questions": ilk["questions"],
                              "followup_rounds": 1})
        bilgi(f"süre: {time.perf_counter() - t:.1f} sn   durum: {son['status']}")
        bilgi(json.dumps(son["brief"], ensure_ascii=False, indent=2), girinti=8)
        kontrol(son["status"] == "final", "gerçek modelle brief tamamlandı")

bitir()
