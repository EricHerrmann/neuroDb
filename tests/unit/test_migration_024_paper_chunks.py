"""Unit tests for migration 024: paper_chunks + papers.full_text_status/text_source."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from neurodb.db import _MIGRATIONS, _migration_024_paper_chunks
from neurodb.migrations import apply_migrations, get_schema_version
from neurodb.schema import Base


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_migration_024_registered():
    assert _MIGRATIONS.get(24) is _migration_024_paper_chunks


def test_adds_columns_and_table_idempotently():
    eng = _make_engine()
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE papers (id INTEGER PRIMARY KEY, title TEXT)"))
        _migration_024_paper_chunks(conn)
        _migration_024_paper_chunks(conn)  # second run must not raise
        conn.commit()
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("papers")}
    assert {"full_text_status", "text_source"} <= cols
    assert "paper_chunks" in insp.get_table_names()


def test_full_chain_includes_024():
    eng = _make_engine()
    Base.metadata.create_all(eng)
    apply_migrations(eng, _MIGRATIONS)
    assert get_schema_version(eng) >= 24
    assert "paper_chunks" in inspect(eng).get_table_names()
