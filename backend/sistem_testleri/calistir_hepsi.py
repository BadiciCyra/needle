"""Tüm sistem test script'lerini sırayla çalıştırır ve özet tablo basar.

Çalıştırma:  python sistem_testleri/calistir_hepsi.py [--gercek] [--veritabanisiz]
  --gercek         LLM isteyen script'ler gerçek OmniRoute'u kullanır
  --veritabanisiz  Docker gerektiren 04 ve 10'u atlar
"""

import subprocess
import sys
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
VERITABANI = {"04_veritabani.py", "10_api.py"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

scriptler = sorted(p for p in KLASOR.glob("[0-9][0-9]_*.py"))
ek = [a for a in sys.argv[1:] if a == "--gercek"]
sonuclar = []
for script in scriptler:
    if "--veritabanisiz" in sys.argv and script.name in VERITABANI:
        sonuclar.append((script.name, "ATLANDI", 0.0))
        continue
    print(f"\n######## {script.name} ########", flush=True)
    t = time.perf_counter()
    kod = subprocess.call([sys.executable, str(script), *ek], cwd=KLASOR.parent)
    sonuclar.append((script.name, "GEÇTİ" if kod == 0 else "BAŞARISIZ", time.perf_counter() - t))

print("\n" + "=" * 50)
print(f"  {'script':<26}{'sonuç':<12}süre")
print("=" * 50)
for ad, durum, sure in sonuclar:
    print(f"  {ad:<26}{durum:<12}{sure:5.1f} sn")
basarisiz = [s for s in sonuclar if s[1] == "BAŞARISIZ"]
atlanan = [s for s in sonuclar if s[1] == "ATLANDI"]
calisan = len(sonuclar) - len(atlanan)
print("=" * 50)
print(f"  {calisan - len(basarisiz)}/{calisan} çalışan script geçti" + (f", {len(atlanan)} atlandı" if atlanan else ""))
sys.exit(1 if basarisiz else 0)
