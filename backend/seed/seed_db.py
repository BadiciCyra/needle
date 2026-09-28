"""Veritabanını kurar ve 40 girişim profilini embedding'leriyle yükler.

Kullanım (backend klasöründen):
    python -m seed.seed_db

Tekrar çalıştırmak güvenlidir: aynı id'li girişimler güncellenir.
"""

from sqlalchemy.dialects.postgresql import insert

from app.db.models import Startup
from app.db.session import get_session_factory, init_db
from app.embeddings import get_embedder
from app.seed_data import load_startups


def seed_startups() -> int:
    init_db()
    startups = load_startups()
    vectors = get_embedder().embed_documents([s.to_search_text() for s in startups])

    rows = [
        {
            "id": s.id,
            "name": s.name,
            "sector": s.sector,
            "maturity": s.maturity.value,
            "location": s.location,
            "capabilities": s.capabilities,
            "description": s.description,
            "past_pilots": s.past_pilots,
            "embedding": vector,
        }
        for s, vector in zip(startups, vectors)
    ]
    statement = insert(Startup).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[Startup.id],
        set_={c: statement.excluded[c] for c in rows[0] if c != "id"},
    )
    with get_session_factory()() as session:
        session.execute(statement)
        session.commit()
    return len(rows)


if __name__ == "__main__":
    count = seed_startups()
    print(f"{count} girişim yüklendi.")
