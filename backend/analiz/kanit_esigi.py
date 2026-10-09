"""Kanıt eşiği analizi: gerekçe izindeki ifade ile yetkinlik arasındaki benzerlik doğru ve uydurma bağları ayırıyor mu?

Fikir 2'nin ilk adımı. Kod değiştirmeden önce veriye bakıyoruz:
  1. Elle etiketlenmiş 30 ifade–yetkinlik çifti okunur (analiz/kanit_ciftleri.json):
     14 doğru bağ, 8 rastgele uydurma, 8 tuzak (ortak kelime var ama anlam farklı).
  2. Her çift için embedding benzerliği (kosinüs) hesaplanır.
  3. Farklı eşik değerlerinde kaç doğru bağın korunduğu, kaç uydurmanın atıldığı ölçülür.

LLM gerekmez: benzerliği yerel embedding modeli hesaplar.

Çalıştırma (backend klasöründen):
    python analiz/kanit_esigi.py           # gerçek yerel modelle
    python analiz/kanit_esigi.py --sahte   # sadece script'in çalıştığını kontrol eder, sayılar anlamsız
"""

import json
import statistics
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import get_settings  # noqa: E402
from app.embeddings import cosine  # noqa: E402

CIFT_DOSYA = Path(__file__).resolve().parent / "kanit_ciftleri.json"
ESIKLER = (0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70)


def puanla(embedder, ciftler: list[dict]) -> list[dict]:
    metinler = sorted({c["brief_phrase"] for c in ciftler} | {c["startup_capability"] for c in ciftler})
    vektorler = dict(zip(metinler, embedder.embed_documents(metinler)))
    for c in ciftler:
        c["skor"] = cosine(vektorler[c["brief_phrase"]], vektorler[c["startup_capability"]])
    return ciftler


def cift_tablosu(ciftler: list[dict]) -> None:
    print("\n1) ÇİFTLER (skora göre büyükten küçüğe)   D = doğru bağ, R = rastgele uydurma, T = tuzak")
    isaret = {"dogru": "D", "rastgele": "R", "tuzak": "T"}
    for c in sorted(ciftler, key=lambda c: c["skor"], reverse=True):
        print(f"   {c['skor']:.3f}  {isaret[c['tur']]}  {c['id']}  {c['brief_phrase'][:42]:<42} ↔ {c['startup_capability']}")


def dagilim(ciftler: list[dict]) -> None:
    print("\n2) TÜRLERE GÖRE SKOR")
    for tur in ("dogru", "tuzak", "rastgele"):
        skorlar = [c["skor"] for c in ciftler if c["tur"] == tur]
        print(
            f"   {tur:<9} adet {len(skorlar):>2}  en düşük {min(skorlar):.3f}  "
            f"medyan {statistics.median(skorlar):.3f}  en yüksek {max(skorlar):.3f}"
        )
    dogru_min = min(c["skor"] for c in ciftler if c["tur"] == "dogru")
    uydurma_max = max(c["skor"] for c in ciftler if c["tur"] != "dogru")
    if dogru_min > uydurma_max:
        print(f"   → Tam ayrılıyor: {uydurma_max:.3f} ile {dogru_min:.3f} arasındaki her eşik kusursuz çalışır.")
        print(f"     Ortası: {(uydurma_max + dogru_min) / 2:.3f}")
    else:
        ortak = sum(c["skor"] <= uydurma_max for c in ciftler if c["tur"] == "dogru")
        print(f"   → Üst üste biniyor: {ortak} doğru bağın skoru en yüksek uydurmadan ({uydurma_max:.3f}) düşük.")


def esik_tablosu(ciftler: list[dict]) -> None:
    mevcut = getattr(get_settings(), "evidence_min_similarity", None)
    dogru = [c for c in ciftler if c["tur"] == "dogru"]
    tuzak = [c for c in ciftler if c["tur"] == "tuzak"]
    rastgele = [c for c in ciftler if c["tur"] == "rastgele"]
    print("\n3) EŞİK TARAMASI")
    print("   doğru korundu : doğru bağların kaçı eşiği geçti (yüksek olmalı; düşükse iyi gerekçeler siliniyor)")
    print("   atıldı        : uydurma bağların kaçı elendi (yüksek olmalı)")
    print(f"\n   {'eşik':<8}{'doğru korundu':<16}{'tuzak atıldı':<15}{'rastgele atıldı'}")
    for esik in ESIKLER:
        d = sum(c["skor"] >= esik for c in dogru)
        t = sum(c["skor"] < esik for c in tuzak)
        r = sum(c["skor"] < esik for c in rastgele)
        not_ = "  ← şu anki ayar" if mevcut is not None and abs(esik - mevcut) < 1e-9 else ""
        print(f"   {esik:<8.2f}{f'{d}/{len(dogru)}':<16}{f'{t}/{len(tuzak)}':<15}{r}/{len(rastgele)}{not_}")


def main() -> None:
    if "--sahte" in sys.argv:
        from app.embeddings import HashingEmbedder

        embedder = HashingEmbedder()
        print("SAHTE MOD: sadece script'in çalıştığını kontrol eder, sayılar anlamsız.")
    else:
        from app.embeddings import get_embedder

        embedder = get_embedder()
        print("Model yükleniyor (ilk çalıştırmada indirilir)...")

    ciftler = puanla(embedder, json.loads(CIFT_DOSYA.read_text(encoding="utf-8")))
    cift_tablosu(ciftler)
    dagilim(ciftler)
    esik_tablosu(ciftler)


if __name__ == "__main__":
    main()
