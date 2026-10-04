"""Eşik analizi: reranker skorları doğru ve yanlış adaylar arasında nasıl dağılıyor?

Fikir 1'in (güven eşiği) ilk adımı. Kod değiştirmeden önce veriye bakıyoruz:
  1. Her ihtiyaç için aday bulunur ve çok dilli cross-encoder ile puanlanır.
  2. Doğru girişimin skoru ile kısa listedeki diğer adayların skorları yan yana yazılır.
  3. Farklı eşik kurallarının kaç doğru adayı tuttuğu, kaç gürültüyü attığı ölçülür.

Not: Ham ihtiyaç metni kullanılır (brief adımı yok), bu yüzden LLM gerekmez.
Gerçek sistemde reranker brief metnini görür; LLM bağlandığında bu analiz brief'lerle tekrarlanmalı.

Çalıştırma (backend klasöründen):
    python analiz/esik_analizi.py           # gerçek yerel modellerle
    python analiz/esik_analizi.py --sahte   # sadece script'in çalıştığını kontrol eder, sayılar anlamsız
"""

import statistics
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.retrieval.base import SearchQuery  # noqa: E402
from app.retrieval.memory import InMemoryRetriever  # noqa: E402
from app.seed_data import load_needs, load_startups  # noqa: E402

# Her ihtiyacın "doğru" girişimi (sistem_testleri/07_reranker.py ile aynı etiketler)
DOGRU = {
    "n01": "s01", "n02": "s06", "n03": "s10", "n04": "s17", "n05": "s27", "n06": "s23", "n07": "s33",
    "n08": "s29", "n09": "s14", "n10": "s07", "n11": "s02", "n12": "s08", "n13": "s09", "n14": "s03",
    "n15": "s12", "n16": "s35", "n17": "s15", "n18": "s38", "n19": "s25", "n20": "s37",
}
HAVUZ = 20       # reranker'a giden aday sayısı (match_graph'taki retrieve_top_k ile aynı)
KISA_LISTE = 5   # bugünkü sabit kısa liste boyu


def topla(embedder, reranker) -> list[dict]:
    """Her ihtiyaç için kısa listeyi (ilk 5) skorlarıyla döndürür."""
    retriever = InMemoryRetriever(load_startups(), embedder)
    satirlar = []
    for need in load_needs():
        metin = need["raw_text"]
        adaylar = retriever.search(SearchQuery(label="ham", vector=embedder.embed_query(metin), top_k=HAVUZ))
        sirali = reranker.rerank(metin, adaylar)
        satirlar.append(
            {
                "id": need["id"],
                "dogru": DOGRU[need["id"]],
                "kisa": [(c.startup.id, c.rerank_score) for c in sirali[:KISA_LISTE]],
            }
        )
    return satirlar


def ihtiyac_tablosu(satirlar: list[dict]) -> None:
    print("\n1) İHTİYAÇ BAZINDA KISA LİSTE SKORLARI   (* = doğru girişim)")
    print(f"   {'ihtiyaç':<8}{'doğru sıra':<12}" + "".join(f"{i + 1}. aday{'':<5}" for i in range(KISA_LISTE)))
    for s in satirlar:
        ids = [sid for sid, _ in s["kisa"]]
        sira = ids.index(s["dogru"]) + 1 if s["dogru"] in ids else "-"
        hucreler = "".join(
            f"{('*' if sid == s['dogru'] else ' ')}{skor:.3f}{'':<8}" for sid, skor in s["kisa"]
        )
        print(f"   {s['id']:<8}{str(sira):<12}{hucreler}")


def dagilim(satirlar: list[dict]) -> tuple[list[float], list[float]]:
    dogru, yanlis = [], []
    for s in satirlar:
        for sid, skor in s["kisa"]:
            (dogru if sid == s["dogru"] else yanlis).append(skor)

    print("\n2) SKOR DAĞILIMI   (D = doğru aday, Y = kısa listedeki yanlış aday)")
    for alt in [i / 10 for i in range(9, -1, -1)]:
        d = sum(alt <= x < alt + 0.1 or (alt == 0.9 and x >= 1.0) for x in dogru)
        y = sum(alt <= x < alt + 0.1 or (alt == 0.9 and x >= 1.0) for x in yanlis)
        print(f"   {alt:.1f}–{alt + 0.1:.1f} | D {'█' * min(d, 20):<20} {d:>2}  | Y {'█' * min(y, 40):<40} {y:>2}")
    for ad, liste in (("doğru", dogru), ("yanlış", yanlis)):
        if liste:
            print(
                f"   {ad:<7} adet {len(liste):>3}  en düşük {min(liste):.3f}  "
                f"medyan {statistics.median(liste):.3f}  en yüksek {max(liste):.3f}"
            )
    return dogru, yanlis


def degerlendir(satirlar: list[dict], tut) -> dict:
    """tut(skor, birinci_skor) -> bool kuralını uygular, sonuçları sayar."""
    dogru_vardi = dogru_kaldi = yanlis_vardi = yanlis_atildi = bos = 0
    boylar = []
    for s in satirlar:
        birinci = s["kisa"][0][1]
        kalan = [(sid, skor) for sid, skor in s["kisa"] if tut(skor, birinci)]
        boylar.append(len(kalan))
        bos += not kalan
        for sid, skor in s["kisa"]:
            kaldi = (sid, skor) in kalan
            if sid == s["dogru"]:
                dogru_vardi += 1
                dogru_kaldi += kaldi
            else:
                yanlis_vardi += 1
                yanlis_atildi += not kaldi
    return {
        "dogru": f"{dogru_kaldi}/{dogru_vardi}",
        "yanlis": f"{yanlis_atildi}/{yanlis_vardi}",
        "boy": statistics.mean(boylar),
        "bos": bos,
    }


def esik_tablosu(satirlar: list[dict]) -> None:
    print("\n3) EŞİK KURALLARININ KARŞILAŞTIRMASI")
    print("   doğru tutuldu : kısa listede olan doğru adayların kaçı eşikten geçti (yüksek olmalı)")
    print("   yanlış atıldı : kısa listedeki yanlış adayların kaçı elendi (yüksek olmalı)")
    print("   boş liste     : hiç aday kalmayan ihtiyaç (bu veride hepsinin doğru cevabı var → hatalı 'uygun yok')")
    baslik = f"   {'kural':<26}{'doğru tutuldu':<16}{'yanlış atıldı':<16}{'ort. liste':<12}{'boş liste'}"

    def yaz(ad, sonuc):
        print(f"   {ad:<26}{sonuc['dogru']:<16}{sonuc['yanlis']:<16}{sonuc['boy']:<12.1f}{sonuc['bos']}")

    print("\n   a) Mutlak eşik: skor ≥ t")
    print(baslik)
    yaz("eşik yok (bugünkü hali)", degerlendir(satirlar, lambda skor, birinci: True))
    for t in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        yaz(f"skor ≥ {t:.1f}", degerlendir(satirlar, lambda skor, birinci, t=t: skor >= t))

    print("\n   b) Göreli eşik: skor ≥ r × birincinin skoru")
    print(baslik)
    for r in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        yaz(f"skor ≥ {r:.1f} × birinci", degerlendir(satirlar, lambda skor, birinci, r=r: skor >= r * birinci))


def main() -> None:
    if "--sahte" in sys.argv:
        from app.embeddings import HashingEmbedder
        from app.rerank.rerankers import PassthroughReranker

        embedder, reranker = HashingEmbedder(), PassthroughReranker()
        print("SAHTE MOD: sadece script'in çalıştığını kontrol eder, sayılar anlamsız.")
    else:
        from app.config import get_settings
        from app.embeddings import get_embedder
        from app.rerank.rerankers import CrossEncoderReranker

        embedder, reranker = get_embedder(), CrossEncoderReranker(get_settings().rerank_model)
        print("Modeller yükleniyor (ilk çalıştırmada indirilir)...")

    satirlar = topla(embedder, reranker)
    ihtiyac_tablosu(satirlar)
    dagilim(satirlar)
    esik_tablosu(satirlar)


if __name__ == "__main__":
    main()
