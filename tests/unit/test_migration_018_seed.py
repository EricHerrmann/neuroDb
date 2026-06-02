"""Migration 018 seeds the plasticity/stroke hierarchy on groupings (3a)."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.db import _migration_018_seed_grouping_hierarchy, _MIGRATIONS


def _now():
    return datetime.now(timezone.utc).isoformat()


def _make_engine():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def _seed_topics(engine, names):
    with engine.connect() as conn:
        for n in names:
            conn.execute(text(
                "INSERT INTO groupings (type, name, parent_id, status, created_at, updated_at) "
                "VALUES ('topic', :n, NULL, 'active', :now, :now)"
            ), {"n": n, "now": _now()})
        conn.commit()


def test_migration_018_registered():
    assert _MIGRATIONS.get(18) is _migration_018_seed_grouping_hierarchy


def test_creates_plasticity_and_sets_parents():
    engine = _make_engine()
    _seed_topics(engine, ["neuroplasticity", "stroke", "stroke recovery", "unrelated"])
    with engine.connect() as conn:
        _migration_018_seed_grouping_hierarchy(conn)
        conn.commit()
    with engine.connect() as conn:
        plasticity_id = conn.execute(text(
            "SELECT id FROM groupings WHERE type='topic' AND name='plasticity'"
        )).fetchone()[0]
        np_parent = conn.execute(text(
            "SELECT parent_id FROM groupings WHERE name='neuroplasticity'"
        )).fetchone()[0]
        stroke_id = conn.execute(text(
            "SELECT id FROM groupings WHERE name='stroke'"
        )).fetchone()[0]
        sr_parent = conn.execute(text(
            "SELECT parent_id FROM groupings WHERE name='stroke recovery'"
        )).fetchone()[0]
        unrelated_parent = conn.execute(text(
            "SELECT parent_id FROM groupings WHERE name='unrelated'"
        )).fetchone()[0]
    assert np_parent == plasticity_id
    assert sr_parent == stroke_id
    assert unrelated_parent is None


def test_idempotent():
    engine = _make_engine()
    _seed_topics(engine, ["neuroplasticity"])
    with engine.connect() as conn:
        _migration_018_seed_grouping_hierarchy(conn)
        conn.commit()
    with engine.connect() as conn:
        _migration_018_seed_grouping_hierarchy(conn)
        conn.commit()
        n = conn.execute(text(
            "SELECT COUNT(*) FROM groupings WHERE name='plasticity'"
        )).fetchone()[0]
    assert n == 1
