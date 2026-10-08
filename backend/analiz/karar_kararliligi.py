"""Karar kararlılığı: aynı brief'i defalarca eşleştirince kısa liste ve "uygun yok" kararı değişiyor mu?

Sonuç veritabanına KAYDEDİLMEZ. Gerçek LLM anahtarı ve dolu veritabanı gerekir.

Çalıştırma (backend klasöründen ya da api konteynerinde):
    python analiz/karar_kararliligi.py 4 5 7 3       # her brief 4 kez, brief id'leri
"""

import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import get_settings  # noqa: E402
from app.db.models import BriefRecord  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.embeddings import get_embedder  # noqa: E402
from app.graphs.match_graph import build_match_graph  # noqa: E402
from app.llm.client import get_structured_llm  # noqa: E402
from app.rerank.rerankers import get_reranker  # noqa: E402
from app.retrieval.pgvector import PgVectorRetriever  # noqa: E402


def main() -> None:
    runs, *brief_ids = map(int, sys.argv[1:] or ["4", "5", "7", "3"])
    settings = get_settings()
    llm, embedder = get_structured_llm(), get_embedder()
    reranker = get_reranker(settings, llm)
    with get_session_factory()() as db:
        for bid in brief_ids:
            rec = db.get(BriefRecord, bid)
            outcomes = []
            for _ in range(runs):
                result = build_match_graph(PgVectorRetriever(db), embedder, reranker, llm, settings).invoke(
                    {"brief": rec.data}
                )["result"]
                outcomes.append(tuple(sorted(i.startup.name for i in result.shortlist)) or ("— uygun yok —",))
            counts = Counter(outcomes)
            print(f"\n[{bid}] {rec.data['title']}: {len(counts)} farklı sonuç / {runs} çalıştırma")
            for shortlist, n in counts.most_common():
                print(f"   {n}×  {', '.join(shortlist)}")


if __name__ == "__main__":
    main()
