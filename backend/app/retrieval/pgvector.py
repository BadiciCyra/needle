"""Postgres + pgvector retriever."""

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import Startup
from app.retrieval.base import SearchQuery, maturities_at_least
from app.schemas import Candidate, Maturity, StartupProfile


def build_statement(query: SearchQuery) -> Select:
    distance = Startup.embedding.cosine_distance(query.vector).label("distance")
    statement = select(Startup, distance).where(Startup.embedding.is_not(None))
    if query.filters.exclude_ids:
        statement = statement.where(Startup.id.not_in(sorted(query.filters.exclude_ids)))
    if query.filters.location:
        statement = statement.where(Startup.location == query.filters.location)
    allowed = maturities_at_least(query.filters.min_maturity)
    if allowed:
        statement = statement.where(Startup.maturity.in_(allowed))
    return statement.order_by(distance).limit(query.top_k)


def to_profile(row: Startup) -> StartupProfile:
    return StartupProfile(
        id=row.id,
        name=row.name,
        sector=row.sector,
        maturity=Maturity(row.maturity),
        location=row.location,
        capabilities=row.capabilities,
        description=row.description,
        past_pilots=row.past_pilots or [],
        website=row.website,
    )


class PgVectorRetriever:
    def __init__(self, session: Session):
        self.session = session

    def search(self, query: SearchQuery) -> list[Candidate]:
        rows = self.session.execute(build_statement(query)).all()
        return [Candidate(startup=to_profile(row.Startup), vector_score=1.0 - float(row.distance)) for row in rows]
