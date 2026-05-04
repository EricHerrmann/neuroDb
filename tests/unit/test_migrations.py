import pytest
from sqlalchemy import create_engine, text
from neurodb.migrations import apply_migrations, get_schema_version


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
