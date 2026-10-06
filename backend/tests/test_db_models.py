from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.db.models import Base


def test_all_tables_are_defined():
    assert set(Base.metadata.tables) == {
        "organizations",
        "needs",
        "briefs",
        "startups",
        "match_runs",
        "matches",
        "pilots",
        "milestones",
        "users",
        "auth_sessions",
    }


def test_tables_compile_for_postgres_with_vector_columns():
    ddl = str(CreateTable(Base.metadata.tables["startups"]).compile(dialect=postgresql.dialect()))
    assert "VECTOR(384)" in ddl
    assert "JSONB" in ddl
