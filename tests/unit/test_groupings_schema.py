"""Unit tests for the unified groupings/grouping_links ORM models."""
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base


def _now():
    return datetime.now(UTC).isoformat()


def _make_engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


def test_groupings_table_created_and_insertable():
    engine = _make_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO groupings "
            "(type, name, parent_id, status, description, created_at, updated_at) "
            "VALUES ('topic', 'plasticity', NULL, 'active', NULL, :now, :now)"
        ), {"now": _now()})
        conn.commit()
        row = conn.execute(text(
            "SELECT type, name, status FROM groupings WHERE name='plasticity'"
        )).fetchone()
    assert row == ("topic", "plasticity", "active")


def test_groupings_type_name_unique():
    engine = _make_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO groupings (type, name, status, created_at, updated_at) "
            "VALUES ('topic', 'stroke', 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(text(
                "INSERT INTO groupings (type, name, status, created_at, updated_at) "
                "VALUES ('topic', 'stroke', 'active', :now, :now)"
            ), {"now": _now()})
            conn.commit()


def test_same_name_different_type_allowed():
    engine = _make_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO groupings (type, name, status, created_at, updated_at) VALUES "
            "('topic', 'memory', 'active', :now, :now), "
            "('concept', 'memory', 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()
        n = conn.execute(text("SELECT COUNT(*) FROM groupings WHERE name='memory'")).fetchone()[0]
    assert n == 2


def test_grouping_links_table_created_and_unique_anchor():
    engine = _make_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at) "
            "VALUES (1, 'question', 14, 'pending', :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(text(
                "INSERT INTO grouping_links "
                "(grouping_id, anchor_type, anchor_id, status, created_at) "
                "VALUES (1, 'question', 14, 'confirmed', :now)"
            ), {"now": _now()})
            conn.commit()
