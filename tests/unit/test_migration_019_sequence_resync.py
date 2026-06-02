"""Migration 019 resyncs grouping id sequences past explicit-id backfill (DuckDB).

Regression for the agent-proposed-grouping primary-key collision: migrations
017/018 insert rows with explicit ids without advancing the DuckDB sequence, so
the ORM insert path (nextval) collided with backfilled rows.
"""
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.db import _migration_019_resync_grouping_sequences, _MIGRATIONS
from neurodb.db.grouping_store import get_or_create_grouping


def _now():
    return datetime.now(timezone.utc).isoformat()


def test_migration_019_registered():
    assert _MIGRATIONS.get(19) is _migration_019_resync_grouping_sequences


def test_resync_lets_orm_insert_after_explicit_id_backfill_duckdb():
    eng = create_engine("duckdb:///:memory:")
    Base.metadata.create_all(eng)
    # Simulate the explicit-id backfill done by migrations 017/018.
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO groupings (id, type, name, parent_id, status, description, created_at, updated_at) "
            "VALUES (1, 'topic', 'a', NULL, 'active', NULL, :now, :now), "
            "(2, 'concept', 'b', NULL, 'active', NULL, :now, :now)"
        ), {"now": _now()})
    # Resync the sequences past the max backfilled id.
    with eng.connect() as conn:
        _migration_019_resync_grouping_sequences(conn)
        conn.commit()
    # The ORM insert path (nextval) must now allocate an id beyond the backfill.
    with Session(eng) as s:
        g = get_or_create_grouping(s, "topic", "c")
        s.commit()
        assert g.id >= 3


def test_migration_019_noop_on_sqlite():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    with eng.connect() as conn:
        _migration_019_resync_grouping_sequences(conn)  # must not raise
        conn.commit()
