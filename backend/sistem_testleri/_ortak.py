"""Sistem test script'lerinin ortak yardımcıları.

Her script tek başına çalışır:  python sistem_testleri/01_ayarlar.py
Kontrollerden biri başarısız olursa script 1 koduyla biter.
"""

import sys
import warnings
from pathlib import Path

# backend/ klasörünü import yoluna ekle (script'ler nereden çalıştırılırsa çalıştırılsın)
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Windows konsolunda Türkçe karakterler bozulmasın
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

warnings.filterwarnings("ignore")

_hatalar: list[str] = []


def baslik(metin: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {metin}")
    print("=" * 78)


def adim(numara: int | str, metin: str) -> None:
    print(f"\n--- Adım {numara}: {metin}")


def bilgi(metin: str = "", girinti: int = 4) -> None:
    for satir in str(metin).splitlines() or [""]:
        print(" " * girinti + satir)


def kontrol(kosul: bool, aciklama: str) -> bool:
    if kosul:
        print(f"    ✓ {aciklama}")
    else:
        print(f"    ✗ {aciklama}")
        _hatalar.append(aciklama)
    return kosul


def gercek_mod() -> bool:
    """--gercek bayrağı verildiyse gerçek LLM (OmniRoute) kullanılır."""
    return "--gercek" in sys.argv


def bitir() -> None:
    print("\n" + "-" * 78)
    if _hatalar:
        print(f"  SONUÇ: {len(_hatalar)} kontrol BAŞARISIZ")
        for hata in _hatalar:
            print(f"    - {hata}")
        sys.exit(1)
    print("  SONUÇ: tüm kontroller geçti")
    sys.exit(0)


class SiraliSahteLLM:
    """Önceden yazılmış cevapları sırayla döndüren sahte model. Her çağrıyı kaydeder."""

    model_name = "sahte-model"

    def __init__(self, cevaplar: list[str]):
        self.cevaplar = list(cevaplar)
        self.cagrilar: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> str:
        self.cagrilar.append(messages)
        if not self.cevaplar:
            raise AssertionError("SiraliSahteLLM: beklenenden fazla çağrı yapıldı")
        return self.cevaplar.pop(0)


def ozetle(metin: str, uzunluk: int = 300) -> str:
    metin = metin.replace("\n", " ")
    return metin if len(metin) <= uzunluk else metin[:uzunluk] + " …"
