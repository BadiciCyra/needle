"""SİSTEM 1 — Ayarlar (app/config.py)

Ne gösterir:
  1. Ayarların .env'den mi yoksa varsayılandan mı geldiği
  2. Ortam değişkeninin .env'i ezdiği (öncelik sırası)
  3. Literal tipli ayara geçersiz değer verilince programın hata verdiği
  4. get_settings()'in önbellekli olduğu (hep aynı nesneyi döndürdüğü)

Çalıştırma:  python sistem_testleri/01_ayarlar.py
"""

import os

from _ortak import adim, baslik, bilgi, bitir, kontrol

from pydantic import ValidationError

from app.config import Settings, get_settings

baslik("SİSTEM 1 — AYARLAR (app/config.py)")

adim(1, "Ayarları oku ve her birinin nereden geldiğini göster")
varsayilan = Settings.model_fields
ayarlar = Settings()
for ad, alan in varsayilan.items():
    deger = getattr(ayarlar, ad)
    kaynak = "varsayılan" if deger == alan.default else ".env / ortam"
    bilgi(f"{ad:<24} = {str(deger):<60} [{kaynak}]")
kontrol(ayarlar.embedding_dim == 384, "embedding boyutu 384 (modelin ürettiği vektör uzunluğu)")
kontrol(ayarlar.shortlist_size + ayarlar.rejected_size == ayarlar.min_candidates,
        "min_candidates = kısa liste + elenen (5 + 3 = 8)")
kontrol("127.0.0.1" in ayarlar.database_url, "veritabanı adresi localhost değil 127.0.0.1 (Windows IPv6 gecikmesi)")

adim(2, "Ortam değişkeni .env'den önce gelir")
os.environ["RETRIEVE_TOP_K"] = "50"
try:
    kontrol(Settings().retrieve_top_k == 50, "RETRIEVE_TOP_K=50 ortam değişkeni ayarı ezdi")
finally:
    del os.environ["RETRIEVE_TOP_K"]
kontrol(Settings().retrieve_top_k == 20, "ortam değişkeni silinince tekrar varsayılana (20) döndü")

adim(3, "Geçersiz değer verilince program açılmadan hata verir (Literal)")
for alan, yanlis in [("DEMO_MODE", "replai"), ("RERANK_BACKEND", "gpt")]:
    os.environ[alan] = yanlis
    try:
        Settings()
        kontrol(False, f"{alan}={yanlis} reddedilmeliydi")
    except ValidationError as hata:
        kontrol(True, f"{alan}={yanlis} reddedildi")
        bilgi(f"pydantic hatası: {str(hata).splitlines()[1].strip()}", girinti=8)
    finally:
        del os.environ[alan]

adim(4, "get_settings() önbellekli: .env bir kez okunur")
kontrol(get_settings() is get_settings(), "iki çağrı aynı nesneyi döndürdü (lru_cache)")
kontrol(Settings() is not Settings(), "Settings() ise her seferinde yeni nesne üretir")

bitir()
