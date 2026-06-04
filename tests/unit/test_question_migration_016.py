"""Unit test for migration 016 — question_topics/question_concepts tables and backfill (T3)."""
from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from neurodb.db import _migration_016_question_topic_tables
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


def _create_topics_table(conn):
    """Create the legacy topics table for tests that seed topic rows.

    Base.metadata.create_all no longer creates it (the Topic ORM model was
    removed in Groupings Phase 5); these migration-016 tests still need a
    topics table to seed a topic_id value.
    """
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY, name VARCHAR(256) NOT NULL,
            description TEXT, status VARCHAR(16) NOT NULL DEFAULT 'active',
            created_at VARCHAR(32) NOT NULL, updated_at VARCHAR(32) NOT NULL)
    """))


def test_migration_creates_tables():
    engine = _make_engine()
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='question_topics'"
        )).fetchone()
        assert row is not None, "question_topics table not created"
        row = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='question_concepts'"
        )).fetchone()
        assert row is not None, "question_concepts table not created"


def test_migration_adds_origin_session_id():
    engine = _make_engine()
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()
    with engine.connect() as conn:
        # Can insert with origin_session_id without error
        conn.execute(text(
            "INSERT INTO research_questions "
            "(question, topic_context, status, created_at, updated_at, origin_session_id) "
            "VALUES ('q?', '', 'open', :now, :now, NULL)"
        ), {"now": _now()})
        conn.commit()


def test_migration_backfills_existing_topic_id():
    engine = _make_engine()
    # Insert a topic and a question with topic_id set
    with engine.connect() as conn:
        _create_topics_table(conn)
        conn.execute(text(
            "INSERT INTO topics (name, status, created_at, updated_at)"
            " VALUES ('plasticity', 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        topic_id = conn.execute(
            text("SELECT id FROM topics WHERE name='plasticity'")
        ).fetchone()[0]
        conn.execute(text(
            "INSERT INTO research_questions "
            "(question, topic_context, status, created_at, updated_at, topic_id) "
            "VALUES ('q?', '', 'open', :now, :now, :tid)"
        ), {"now": _now(), "tid": topic_id})
        conn.commit()
    with engine.connect() as conn:
        q_id = conn.execute(
            text("SELECT id FROM research_questions WHERE question='q?'")
        ).fetchone()[0]
    # Apply migration
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()
    # Check backfill
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT status FROM question_topics WHERE question_id=:qid AND topic_id=:tid"
        ), {"qid": q_id, "tid": topic_id}).fetchone()
        assert row is not None, "backfill row not created"
        assert row[0] == "confirmed", f"expected 'confirmed', got {row[0]}"


def test_migration_is_idempotent():
    engine = _make_engine()
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()
    # Running twice should not raise
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()


def test_existing_topic_id_fk_preserved():
    engine = _make_engine()
    with engine.connect() as conn:
        _create_topics_table(conn)
        conn.execute(text(
            "INSERT INTO topics (name, status, created_at, updated_at)"
            " VALUES ('plasticity', 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        topic_id = conn.execute(
            text("SELECT id FROM topics WHERE name='plasticity'")
        ).fetchone()[0]
        conn.execute(text(
            "INSERT INTO research_questions "
            "(question, topic_context, status, created_at, updated_at, topic_id) "
            "VALUES ('q?', '', 'open', :now, :now, :tid)"
        ), {"now": _now(), "tid": topic_id})
        conn.commit()
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()
    # topic_id column still exists and has value
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT topic_id FROM research_questions WHERE question='q?'"
        )).fetchone()
        assert row[0] == topic_id, "topic_id FK was removed or cleared"
