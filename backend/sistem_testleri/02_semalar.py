"""SİSTEM 2 — Veri şemaları (app/schemas.py)

Ne gösterir:
  1. Eksik bir Brief'te zorunlu alanların kodla bulunması
  2. LLM'in "eksik yok" beyanının neden yok sayıldığı
  3. Embedding'e giden arama metninin nasıl oluştuğu
  4. LLM'e gönderilen JSON şemasının (alan açıklamaları = modele talimat)
  5. Hatalı veride Pydantic'in nasıl reddettiği

Çalıştırma:  python sistem_testleri/02_semalar.py
"""

import json

from _ortak import adim, baslik, bilgi, bitir, kontrol, ozetle

from pydantic import ValidationError

from app.schemas import REQUIRED_BRIEF_FIELDS, Brief, Maturity, StartupProfile

baslik("SİSTEM 2 — VERİ ŞEMALARI (app/schemas.py)")

adim(1, "Eksik brief: zorunlu alanları kod hesaplar")
bilgi(f"Zorunlu alanlar: {', '.join(REQUIRED_BRIEF_FIELDS)}")
brief = Brief(
    title="Bayi şikayetlerinin sınıflandırılması",
    problem="Bayilerden gelen şikayetler elle sınıflandırılıyor",
    required_capabilities=["Türkçe metin sınıflandırma"],
)
eksik = brief.computed_missing_fields()
bilgi(f"Eksik bulunanlar: {eksik}")
kontrol(eksik == ["scope", "success_criteria", "timeline"], "kapsam, başarı kriteri ve süre eksik bulundu")

adim(2, "LLM 'eksik yok' dese bile kod kendi hesabını yapar")
yalanci = Brief(title="t", problem="p", missing_fields=[])  # model eksik yok diyor
bilgi(f"LLM'in beyanı: missing_fields = {yalanci.missing_fields}")
bilgi(f"Kodun hesabı: {yalanci.computed_missing_fields()}")
kontrol(len(yalanci.computed_missing_fields()) == 4, "kod 4 eksik alan buldu, beyana güvenmedi")

adim(3, "Boş string ve boş liste de 'eksik' sayılır")
bos = Brief(title="t", problem="", scope="s", required_capabilities=[], success_criteria="x", timeline="3 ay")
kontrol(bos.computed_missing_fields() == ["problem", "required_capabilities"], "'' ve [] eksik sayıldı")

adim(4, "Embedding'e giden arama metni")
tam = Brief(title="Bayi şikayetleri", problem="elle sınıflandırılıyor", scope="ayda 3.000 şikayet",
            required_capabilities=["Türkçe metin sınıflandırma", "şikayet kategorizasyonu"], sector="perakende")
bilgi(tam.to_search_text())
kontrol("Türkçe metin sınıflandırma ; şikayet kategorizasyonu" in tam.to_search_text(), "yetkinlikler metne eklendi")
kontrol("Sektör: perakende" in tam.to_search_text(), "sektör metne eklendi")

adim(5, "LLM'e gönderilen JSON şeması (alan açıklamaları modele talimattır)")
sema = Brief.model_json_schema()
for alan in ("required_capabilities", "success_criteria"):
    bilgi(f"{alan}: {ozetle(sema['properties'][alan]['description'], 120)}")
bilgi(f"Şemanın toplam uzunluğu: {len(json.dumps(sema, ensure_ascii=False))} karakter")
kontrol("required_capabilities" in sema["properties"], "şema yetkinlik alanını içeriyor")

adim(6, "Hatalı veri reddedilir")
try:
    StartupProfile(id="x", name="X", sector="s", maturity="unicorn", location="İstanbul", capabilities=[], description="d")
    kontrol(False, "geçersiz olgunluk reddedilmeliydi")
except ValidationError as hata:
    kontrol(True, "olgunluk='unicorn' reddedildi")
    bilgi(f"izin verilenler: {[m.value for m in Maturity]}", girinti=8)
try:
    Brief(problem="başlıksız")
    kontrol(False, "başlıksız brief reddedilmeliydi")
except ValidationError:
    kontrol(True, "zorunlu 'title' alanı olmadan Brief oluşturulamadı")

bitir()
