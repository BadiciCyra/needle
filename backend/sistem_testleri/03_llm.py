"""SİSTEM 3 — LLM katmanı ve demo önbelleği (app/llm/client.py, app/llm/cache.py)

Ne gösterir:
  1. Modele giden mesajların tam hali (system prompta eklenen JSON şeması talimatı)
  2. ```json bloğu ve fazladan metin temizliği
  3. Bozuk cevapta hatanın modele geri söylenip yeniden denenmesi
  4. Deneme hakkı bitince pes edilmesi
  5. record → replay: ikinci seferde modele hiç gidilmemesi
  6. replay'de önbellekte olmayan istek → hata (uydurma yok)
  7. (--gercek) OmniRoute üzerinden gerçek modele tek bir istek

Çalıştırma:  python sistem_testleri/03_llm.py            (çevrimdışı, sahte model)
             python sistem_testleri/03_llm.py --gercek   (OmniRoute + .env'deki model)
"""

import tempfile
import time
from pathlib import Path

from _ortak import SiraliSahteLLM, adim, baslik, bilgi, bitir, gercek_mod, kontrol, ozetle

from app.config import Settings
from app.llm.cache import DemoCacheMiss
from app.llm.client import StructuredLLM, StructuredOutputError, extract_json
from app.schemas import FollowUpQuestions

GECERLI = '{"questions": [{"field": "timeline", "question": "Pilot 3 ay mı, 6 ay mı sürmeli?"}]}'
klasor = tempfile.mkdtemp(prefix="needle_cache_")


def llm_kur(cevaplar, mod="off", deneme=2):
    ayar = Settings(demo_mode=mod, demo_cache_dir=klasor, llm_max_retries=deneme)
    sahte = SiraliSahteLLM(cevaplar)
    return StructuredLLM(sahte, ayar), sahte


baslik("SİSTEM 3 — LLM KATMANI VE DEMO ÖNBELLEĞİ")

adim(1, "Modele giden mesajlar")
llm, sahte = llm_kur([GECERLI])
llm.invoke(FollowUpQuestions, system="Takip soruları hazırla.", user="Eksik alan: timeline")
system, user = sahte.cagrilar[0]
bilgi(f"[system] {ozetle(system['content'], 260)}")
bilgi(f"[user]   {user['content']}")
kontrol("SADECE aşağıdaki JSON şemasına" in system["content"], "system prompta JSON talimatı eklendi")
kontrol('"questions"' in system["content"], "şemanın kendisi de prompta eklendi")

adim(2, "Cevap temizliği (extract_json)")
for ham in ['Tabii!\n```json\n{"a": 1}\n```\nBaşka bir şey?', 'Cevabım: {"a": 1} umarım işe yarar']:
    bilgi(f"ham:    {ham!r}")
    bilgi(f"temiz:  {extract_json(ham)!r}")
    kontrol(extract_json(ham) == '{"a": 1}', "JSON gövdesi doğru çıkarıldı")

adim(3, "Bozuk cevap → hata modele söylenir → yeniden dener")
llm, sahte = llm_kur(["Üzgünüm, JSON veremem.", '{"questions": "liste olmalıydı"}', GECERLI])
sonuc = llm.invoke(FollowUpQuestions, "s", "u")
for i, cagri in enumerate(sahte.cagrilar, 1):
    bilgi(f"çağrı {i}: {len(cagri)} mesaj; son mesaj: {ozetle(cagri[-1]['content'], 110)}")
kontrol(len(sahte.cagrilar) == 3, "3 çağrı yapıldı (2 hata + 1 başarı)")
kontrol("şemaya uymadı" in sahte.cagrilar[1][-1]["content"], "2. çağrıda hata mesajı modele geri verildi")
kontrol(sonuc.questions[0].field == "timeline", "sonunda geçerli cevap alındı")

adim(4, "Deneme hakkı bitince pes eder")
llm, sahte = llm_kur(["x", "y", "z"], deneme=2)
try:
    llm.invoke(FollowUpQuestions, "s", "u")
    kontrol(False, "StructuredOutputError bekleniyordu")
except StructuredOutputError as hata:
    kontrol(len(sahte.cagrilar) == 3, "1 ilk deneme + 2 yeniden deneme = 3 çağrı, sonra pes etti")
    bilgi(ozetle(str(hata), 150), girinti=8)

adim(5, "record → replay")
kaydedici, _ = llm_kur([GECERLI], mod="record")
kaydedici.invoke(FollowUpQuestions, "s", "aynı soru")
dosyalar = list(Path(klasor).glob("*.json"))
bilgi(f"önbellek klasörü: {klasor}  ({len(dosyalar)} dosya)")
oynatici, sahte = llm_kur([], mod="replay")
sonuc = oynatici.invoke(FollowUpQuestions, "s", "aynı soru")
kontrol(len(dosyalar) == 1, "record modunda cevap diske yazıldı")
kontrol(sahte.cagrilar == [], "replay modunda modele hiç gidilmedi")
kontrol(sonuc.questions[0].question.startswith("Pilot"), "önbellekten aynı cevap geldi")

adim(6, "replay'de önbellekte olmayan istek")
oynatici, _ = llm_kur([], mod="replay")
try:
    oynatici.invoke(FollowUpQuestions, "s", "farklı soru")
    kontrol(False, "DemoCacheMiss bekleniyordu")
except DemoCacheMiss:
    kontrol(True, "önbellekte olmayan istek için cevap uydurulmadı, hata verildi")

adim(7, "Gerçek model (--gercek)")
if not gercek_mod():
    bilgi("atlandı: gerçek modeli denemek için --gercek ekle (OmniRoute anahtarı .env'de olmalı)")
else:
    from app.config import get_settings
    from app.llm.client import get_structured_llm

    ayar = get_settings()
    bilgi(f"adres: {ayar.llm_base_url}   model: {ayar.llm_model}")
    baslangic = time.perf_counter()
    try:
        cevap = get_structured_llm().invoke(
            FollowUpQuestions,
            system="Bir kurumun ihtiyaç brief'indeki eksik alanlar için kısa takip soruları yaz.",
            user="İhtiyaç: bayi şikayetlerini sınıflandırmak. Eksik alanlar: scope, timeline",
        )
        bilgi(f"süre: {time.perf_counter() - baslangic:.1f} sn")
        for soru in cevap.questions:
            bilgi(f"[{soru.field}] {soru.question}", girinti=8)
        kontrol(len(cevap.questions) >= 1, "gerçek model şemaya uygun cevap verdi")
    except Exception as hata:
        kontrol(False, f"gerçek model çağrısı başarısız: {ozetle(str(hata), 200)}")

bitir()
