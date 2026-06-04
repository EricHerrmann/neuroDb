"""Unit tests for migration 021: drop legacy topics/concepts tables."""
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from neurodb.db import _MIGRATIONS, _migration_021_drop_legacy_groupings_tables
from neurodb.migrations import apply_migrations, get_schema_version
from neurodb.schema import Base

_LEGACY = (
    "question_topics", "question_concepts", "paper_topics", "paper_concepts",
    "topic_concepts", "dataset_packet_topics", "topics", "concepts",
)


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _table_exists(conn, name):
    return conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": name},
    ).fetchone() is not None


def test_migration_021_registered():
    assert _MIGRATIONS.get(21) is _migration_021_drop_legacy_groupings_tables


def test_drops_existing_legacy_tables():
    eng = _make_engine()
    with eng.connect() as conn:
        for name in _LEGACY:
            conn.execute(text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)"))
        conn.commit()
        _migration_021_drop_legacy_groupings_tables(conn)
        conn.commit()
        for name in _LEGACY:
            assert not _table_exists(conn, name), f"{name} not dropped"


def test_drop_is_idempotent():
    """Running 021 twice must not raise (DROP TABLE IF EXISTS)."""
    eng = _make_engine()
    with eng.connect() as conn:
        _migration_021_drop_legacy_groupings_tables(conn)
        conn.commit()
    with eng.connect() as conn:
        _migration_021_drop_legacy_groupings_tables(conn)
        conn.commit()


def test_fresh_full_migration_run_succeeds_with_legacy_absent():
    eng = _make_engine()
    Base.metadata.create_all(eng)  # legacy models gone -> legacy tables not created
    apply_migrations(eng, _MIGRATIONS)
    assert get_schema_version(eng) >= 21
    with eng.connect() as conn:
        for tbl in ("groupings", "grouping_links"):
            assert _table_exists(conn, tbl)
        for name in _LEGACY:
            assert not _table_exists(conn, name)
