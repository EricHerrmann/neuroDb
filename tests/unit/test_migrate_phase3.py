"""Migration tests use DuckDB in-memory — ALTER COLUMN DROP NOT NULL is DuckDB-only syntax."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

_PRE_MIGRATION_STMTS = [
    "CREATE SEQUENCE IF NOT EXISTS research_questions_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS research_questions (
        id INTEGER DEFAULT nextval('research_questions_id_seq') PRIMARY KEY,
        question TEXT NOT NULL,
        topic_context TEXT NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'open',
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL
    )""",
    "CREATE SEQUENCE IF NOT EXISTS research_hypotheses_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS research_hypotheses (
        id INTEGER DEFAULT nextval('research_hypotheses_id_seq') PRIMARY KEY,
        question_id INTEGER,
        title TEXT NOT NULL,
        mechanism TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        predictions_json TEXT NOT NULL,
        datasets_json TEXT NOT NULL,
        confounds_json TEXT NOT NULL,
        limitations TEXT NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'draft',
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL
    )""",
]


@pytest.fixture
def pre_migration_engine():
    engine = create_engine("duckdb:///:memory:")
    with engine.begin() as conn:
        for stmt in _PRE_MIGRATION_STMTS:
            conn.execute(text(stmt))
    yield engine
    engine.dispose()


def _get_tables(engine) -> set:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='main'"
            )
        ).fetchall()
    return {r[0] for r in rows}


def _get_columns(engine, table: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name, is_nullable FROM information_schema.columns "
                "WHERE table_name = :t ORDER BY ordinal_position"
            ),
            {"t": table},
        ).fetchall()
    return [{"name": r[0], "nullable": r[1] == "YES"} for r in rows]


def test_migration_creates_claims_table(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    assert "claims" in _get_tables(pre_migration_engine)


def test_migration_creates_evidence_links_table(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    assert "evidence_links" in _get_tables(pre_migration_engine)


def test_migration_creates_research_gaps_table(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    assert "research_gaps" in _get_tables(pre_migration_engine)


def test_migration_adds_topic_id_to_research_questions(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    cols = {c["name"] for c in _get_columns(pre_migration_engine, "research_questions")}
    assert "topic_id" in cols


def test_migration_makes_evidence_json_nullable(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    col = next(
        c for c in _get_columns(pre_migration_engine, "research_hypotheses")
        if c["name"] == "evidence_json"
    )
    assert col["nullable"] is True


def test_migration_makes_datasets_json_nullable(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    col = next(
        c for c in _get_columns(pre_migration_engine, "research_hypotheses")
        if c["name"] == "datasets_json"
    )
    assert col["nullable"] is True


def test_migration_makes_confounds_json_nullable(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    col = next(
        c for c in _get_columns(pre_migration_engine, "research_hypotheses")
        if c["name"] == "confounds_json"
    )
    assert col["nullable"] is True


def test_migration_is_idempotent(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    run_migration(pre_migration_engine)  # must not raise
