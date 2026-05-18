"""Migration tests use DuckDB in-memory — ALTER COLUMN DROP NOT NULL is DuckDB-only syntax."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text


def _get_columns(engine, table: str) -> list[dict]:
    """Return column info for *table* using information_schema.

    SQLAlchemy's inspect().get_columns() uses a Postgres-dialect query that
    references pg_collation, which duckdb-engine 0.17.0 does not implement.
    Query information_schema directly — supported by both DuckDB and SQLite.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name AS name, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = :t "
                "ORDER BY ordinal_position"
            ),
            {"t": table},
        ).fetchall()
    return [{"name": r[0], "nullable": r[1] == "YES"} for r in rows]

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))


_PRE_MIGRATION_STMTS = [
    "CREATE SEQUENCE IF NOT EXISTS ingest_runs_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS ingest_runs (
        id INTEGER DEFAULT nextval('ingest_runs_id_seq') PRIMARY KEY,
        source VARCHAR(64) NOT NULL,
        run_at VARCHAR(32) NOT NULL,
        version VARCHAR(32) NOT NULL,
        notes TEXT
    )""",
    "CREATE SEQUENCE IF NOT EXISTS datasets_index_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS datasets_index (
        id INTEGER DEFAULT nextval('datasets_index_id_seq') PRIMARY KEY,
        source VARCHAR(64) NOT NULL,
        source_id VARCHAR(128) NOT NULL,
        run_id INTEGER NOT NULL,
        UNIQUE(source, source_id)
    )""",
    "CREATE SEQUENCE IF NOT EXISTS knowledge_sources_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS knowledge_sources (
        id INTEGER DEFAULT nextval('knowledge_sources_id_seq') PRIMARY KEY,
        title TEXT NOT NULL,
        normalized_title VARCHAR(512) NOT NULL,
        doi VARCHAR(256),
        url TEXT,
        source_type VARCHAR(32) NOT NULL,
        topic_context TEXT NOT NULL,
        status VARCHAR(16) NOT NULL,
        queued_at VARCHAR(32) NOT NULL,
        reviewed_at VARCHAR(32),
        summary TEXT,
        chroma_id VARCHAR(128),
        UNIQUE(normalized_title)
    )""",
    "CREATE SEQUENCE IF NOT EXISTS study_notes_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS study_notes (
        id INTEGER DEFAULT nextval('study_notes_id_seq') PRIMARY KEY,
        index_id INTEGER NOT NULL,
        concept_tag VARCHAR(128) NOT NULL,
        section_ref VARCHAR(64),
        note_text TEXT,
        tagged_at VARCHAR(32) NOT NULL
    )""",
    """INSERT INTO knowledge_sources
        (title, normalized_title, source_type, topic_context, status, queued_at)
        VALUES ('LTP Study', 'ltp study', 'paper', 'plasticity', 'pending', '2026-01-01T00:00:00')
    """,
]


@pytest.fixture
def pre_migration_engine():
    engine = create_engine("duckdb:///:memory:")
    with engine.begin() as conn:
        for stmt in _PRE_MIGRATION_STMTS:
            conn.execute(text(stmt))
    yield engine
    engine.dispose()


def test_rename_knowledge_sources_to_papers(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    tables = set(inspect(pre_migration_engine).get_table_names())
    assert "papers" in tables
    assert "knowledge_sources" not in tables


def test_seeded_row_preserved_in_papers(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    with pre_migration_engine.connect() as conn:
        row = conn.execute(
            text("SELECT title FROM papers WHERE title = 'LTP Study'")
        ).fetchone()
    assert row is not None


def test_papers_has_new_columns(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    cols = {c["name"] for c in _get_columns(pre_migration_engine, "papers")}
    assert {"abstract", "authors_json", "year"}.issubset(cols)


def test_study_notes_index_id_becomes_nullable(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    col = next(
        c for c in _get_columns(pre_migration_engine, "study_notes")
        if c["name"] == "index_id"
    )
    assert col["nullable"] is True


def test_study_notes_has_new_anchor_columns(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    cols = {c["name"] for c in _get_columns(pre_migration_engine, "study_notes")}
    assert {"topic_id", "concept_id", "paper_id"}.issubset(cols)


def test_migration_is_idempotent(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    run_migration(pre_migration_engine)  # must not raise
