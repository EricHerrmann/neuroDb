import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool
from neurodb.migrations import apply_migrations, get_schema_version
from neurodb.db import init_db
from neurodb.schema import Base


def _engine():
    engine = create_engine("sqlite:///:memory:")
    return engine


def test_fresh_db_starts_at_version_zero():
    engine = _engine()
    assert get_schema_version(engine) == 0


def test_apply_migrations_advances_version():
    engine = _engine()
    ran = []

    def migration_1(conn):
        ran.append(1)

    apply_migrations(engine, {1: migration_1})
    assert get_schema_version(engine) == 1
    assert ran == [1]


def test_apply_migrations_is_idempotent():
    engine = _engine()
    ran = []

    def migration_1(conn):
        ran.append(1)

    apply_migrations(engine, {1: migration_1})
    apply_migrations(engine, {1: migration_1})
    assert ran == [1]  # only ran once


def test_apply_migrations_runs_in_version_order():
    engine = _engine()
    order = []

    apply_migrations(engine, {
        2: lambda conn: order.append(2),
        1: lambda conn: order.append(1),
    })
    assert order == [1, 2]


def test_init_db_creates_schema_migrations_table():
    engine = _engine()
    init_db(engine)
    tables = inspect(engine).get_table_names()
    assert "schema_migrations" in tables


def test_migration_008_adds_evidence_links_status():
    """Migration 8 adds status column to evidence_links; idempotent on re-run."""
    from neurodb.migrations import apply_migrations

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    from neurodb.db import _MIGRATIONS

    apply_migrations(engine, {8: _MIGRATIONS[8]})
    apply_migrations(engine, {8: _MIGRATIONS[8]})  # idempotent — must not raise

    # Verify the status column was added to evidence_links
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("evidence_links")}
    assert "status" in columns, "status column should exist on evidence_links"


def test_migration_009_research_questions_archived_guard_is_idempotent():
    """Migration 9 runs without error on a fresh DB (column already present)."""
    from neurodb.migrations import apply_migrations
    from neurodb.db import _MIGRATIONS

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    apply_migrations(engine, {9: _MIGRATIONS[9]})
    apply_migrations(engine, {9: _MIGRATIONS[9]})  # idempotent — must not raise

    # Verify the status column exists on research_questions
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("research_questions")}
    assert "status" in columns, "status column should exist on research_questions"
