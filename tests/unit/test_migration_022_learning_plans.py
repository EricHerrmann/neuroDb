"""Unit tests for migration 022: learning_plans + plan_steps tables."""
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from neurodb.db import _MIGRATIONS, _migration_022_learning_plans
from neurodb.migrations import apply_migrations, get_schema_version
from neurodb.schema import Base


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_migration_022_registered():
    assert _MIGRATIONS.get(22) is _migration_022_learning_plans


def test_creates_tables_idempotently():
    eng = _make_engine()
    with eng.connect() as conn:
        _migration_022_learning_plans(conn)
        _migration_022_learning_plans(conn)  # second run must not raise
        conn.commit()
    names = set(inspect(eng).get_table_names())
    assert {"learning_plans", "plan_steps"} <= names


def test_full_migration_chain_includes_022():
    eng = _make_engine()
    Base.metadata.create_all(eng)
    apply_migrations(eng, _MIGRATIONS)
    assert get_schema_version(eng) >= 22
    names = set(inspect(eng).get_table_names())
    assert {"learning_plans", "plan_steps"} <= names
