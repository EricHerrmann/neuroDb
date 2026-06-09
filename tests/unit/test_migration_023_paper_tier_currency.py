"""Unit tests for migration 023: papers.data_tier + papers.currency_status."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from neurodb.db import _MIGRATIONS, _migration_023_paper_tier_currency
from neurodb.migrations import apply_migrations, get_schema_version
from neurodb.schema import Base


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_migration_023_registered():
    assert _MIGRATIONS.get(23) is _migration_023_paper_tier_currency


def test_adds_columns_idempotently():
    eng = _make_engine()
    with eng.connect() as conn:
        conn.execute(text(
            "CREATE TABLE papers (id INTEGER PRIMARY KEY, title TEXT)"
        ))
        _migration_023_paper_tier_currency(conn)
        _migration_023_paper_tier_currency(conn)  # second run must not raise
        conn.execute(text("INSERT INTO papers (id, title) VALUES (1, 'Test Paper')"))
        row = conn.execute(
            text("SELECT data_tier, currency_status FROM papers WHERE id = 1")
        ).fetchone()
        conn.commit()
    cols = {c["name"] for c in inspect(eng).get_columns("papers")}
    assert {"data_tier", "currency_status"} <= cols
    assert row[0] == "metadata"  # DEFAULT clause populates new rows
    assert row[1] == "current"


def test_full_migration_chain_includes_023():
    eng = _make_engine()
    Base.metadata.create_all(eng)
    apply_migrations(eng, _MIGRATIONS)
    assert get_schema_version(eng) >= 23
    cols = {c["name"] for c in inspect(eng).get_columns("papers")}
    assert {"data_tier", "currency_status"} <= cols
