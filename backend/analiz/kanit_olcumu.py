"""Gerçek LLM gerekçeleriyle kanıt doğrulama ölçümü: kayıtlı brief'lerde izlerin kaçı hangi kontrolde düşüyor?

kanit_esigi.py elle yazılmış çiftlerle ölçüyor; bu script LLM'in gerçekten yazdığı izlere bakar. Sonuç
veritabanına KAYDEDİLMEZ. Gerçek LLM anahtarı ve dolu veritabanı gerekir.

Çalıştırma (backend klasöründen ya da api konteynerinde):
    python analiz/kanit_olcumu.py 2 3 4 5 7      # brief id'leri
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
from app.embeddings import cosine, get_embedder  # noqa: E402
from app.graphs.match_graph import _brief_haystack, _normalize, build_match_graph  # noqa: E402
from app.llm.client import get_structured_llm  # noqa: E402
from app.rerank.rerankers import get_reranker  # noqa: E402
from app.retrieval.pgvector import PgVectorRetriever  # noqa: E402
from app.schemas import RationaleBatch  # noqa: E402


def main() -> None:
    settings = get_settings()
    llm, embedder = get_structured_llm(), get_embedder()
    reranker = get_reranker(settings, llm)

    raw: dict[str, RationaleBatch] = {}
    invoke = llm.invoke

    def spy(schema, **kwargs):
        out = invoke(schema, **kwargs)
        if schema is RationaleBatch:
            raw["batch"] = out.model_copy(deep=True)
        return out

    llm.invoke = spy
    totals = Counter()
    with get_session_factory()() as db:
        for bid in map(int, sys.argv[1:] or ["2", "3", "4", "5", "7"]):
            rec = db.get(BriefRecord, bid)
            result = build_match_graph(PgVectorRetriever(db), embedder, reranker, llm, settings).invoke(
                {"brief": rec.data}
            )["result"]
            haystack = _brief_haystack(rec.data)
            caps = {i.startup.id: {_normalize(c) for c in i.startup.capabilities} for i in result.shortlist}
            print(f"\n[{bid}] {rec.data['title']}")
            for r in raw["batch"].matches:
                for e in r.evidence:
                    if _normalize(e.startup_capability) not in caps.get(r.startup_id, set()):
                        why = "1-yetkinlik profilde yok"
                    elif not _normalize(e.brief_phrase) or _normalize(e.brief_phrase) not in haystack:
                        why = "2-ifade brief'te yok"
                    else:
                        a, b = embedder.embed_documents([e.brief_phrase, e.startup_capability])
                        sim = cosine(a, b)
                        why = f"3-benzerlik {sim:.2f}" if sim < settings.evidence_min_similarity else f"geçti {sim:.2f}"
                    totals[why.split(" ")[0]] += 1
                    print(f"   {why:<26} “{e.brief_phrase}” ↔ {e.startup_capability}")

    print("\nÖZET:", dict(totals))


if __name__ == "__main__":
    main()
