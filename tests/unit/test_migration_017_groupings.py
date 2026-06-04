"""Unit tests for migration 017: unified groupings tables and backfill."""
from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from neurodb.db import _MIGRATIONS, _migration_017_groupings
from neurodb.migrations import apply_migrations, get_schema_version
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


def _create_legacy_tables(conn):
    """Create the legacy source tables the 017 backfill reads, for tests that
    exercise backfill after the ORM models have been removed."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY, name VARCHAR(256) NOT NULL,
            description TEXT, status VARCHAR(16) NOT NULL DEFAULT 'active',
            created_at VARCHAR(32) NOT NULL, updated_at VARCHAR(32) NOT NULL)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS concepts (
            id INTEGER PRIMARY KEY, name VARCHAR(256) NOT NULL,
            description TEXT, status VARCHAR(16) NOT NULL DEFAULT 'active',
            created_at VARCHAR(32) NOT NULL, updated_at VARCHAR(32) NOT NULL)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS question_topics (
            id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL,
            topic_id INTEGER NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at VARCHAR(32) NOT NULL)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS question_concepts (
            id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL,
            concept_id INTEGER NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at VARCHAR(32) NOT NULL)
    """))
    # Link tables: only the columns the 017 backfill reads (no status/timestamps).
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS paper_topics (
            id INTEGER PRIMARY KEY, paper_id INTEGER NOT NULL,
            topic_id INTEGER NOT NULL)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS paper_concepts (
            id INTEGER PRIMARY KEY, paper_id INTEGER NOT NULL,
            concept_id INTEGER NOT NULL)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS topic_concepts (
            id INTEGER PRIMARY KEY, topic_id INTEGER NOT NULL,
            concept_id INTEGER NOT NULL)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS dataset_packet_topics (
            id INTEGER PRIMARY KEY, packet_id INTEGER NOT NULL,
            topic_id INTEGER NOT NULL)
    """))


def test_migration_017_registered():
    assert _MIGRATIONS.get(17) is _migration_017_groupings


def test_migration_runs_without_error_and_tables_exist():
    engine = _make_engine()
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        for tbl in ("groupings", "grouping_links"):
            row = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
            ), {"t": tbl}).fetchone()
            assert row is not None, f"{tbl} missing"


def test_migration_is_idempotent_on_empty_db():
    engine = _make_engine()
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
        n = conn.execute(text("SELECT COUNT(*) FROM groupings")).fetchone()[0]
    assert n == 0


def _seed_topics_concepts(engine):
    with engine.connect() as conn:
        _create_legacy_tables(conn)
        conn.execute(text(
            "INSERT INTO topics (name, description, status, created_at, updated_at) VALUES "
            "('neuroplasticity', 'desc-np', 'active', :now, :now), "
            "('stroke', NULL, 'active', :now, :now)"
        ), {"now": _now()})
        conn.execute(text(
            "INSERT INTO concepts (name, description, status, created_at, updated_at) VALUES "
            "('long-term potentiation', NULL, 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()


def test_backfill_groupings_from_topics_and_concepts():
    engine = _make_engine()
    _seed_topics_concepts(engine)
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT type, name, status, description FROM groupings ORDER BY type, name"
        )).fetchall()
    assert ("topic", "neuroplasticity", "active", "desc-np") in rows
    assert ("topic", "stroke", "active", None) in rows
    assert ("concept", "long-term potentiation", "active", None) in rows
    assert len(rows) == 3


def test_backfill_groupings_idempotent():
    engine = _make_engine()
    _seed_topics_concepts(engine)
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
        n = conn.execute(text("SELECT COUNT(*) FROM groupings")).fetchone()[0]
    assert n == 3


def _seed_links_fixture(engine):
    """Seed topics/concepts plus one row in every legacy link source."""
    with engine.connect() as conn:
        _create_legacy_tables(conn)
        conn.execute(text(
            "INSERT INTO topics (name, status, created_at, updated_at) "
            "VALUES ('stroke', 'active', :now, :now)"
        ), {"now": _now()})
        conn.execute(text(
            "INSERT INTO concepts (name, status, created_at, updated_at) "
            "VALUES ('LTP', 'active', :now, :now)"
        ), {"now": _now()})
        conn.execute(text(
            "INSERT INTO research_questions "
            "(question, topic_context, status, created_at, updated_at) "
            "VALUES ('q?', '', 'open', :now, :now)"
        ), {"now": _now()})
        conn.execute(text(
            "INSERT INTO papers "
            "(title, normalized_title, source_type, topic_context, status, queued_at) "
            "VALUES ('P', 'p', 'paper', '', 'approved', :now)"
        ), {"now": _now()})
        conn.execute(text(
            "INSERT INTO dataset_research_packets ("
            "index_id, source, source_id, usefulness_state, supported_workflows_json, "
            "unsupported_workflows_json, missing_context_json, provenance_json, "
            "confidence_json, harvested_at, run_id"
            ") VALUES (1, 'fixture', 'packet-1', 'useful', '[]', '[]', '[]', '{}', '{}', :now, 1)"
        ), {"now": _now()})
        conn.commit()

    with engine.connect() as conn:
        topic_id = conn.execute(text("SELECT id FROM topics WHERE name='stroke'")).fetchone()[0]
        concept_id = conn.execute(text("SELECT id FROM concepts WHERE name='LTP'")).fetchone()[0]
        q_id = conn.execute(text(
            "SELECT id FROM research_questions WHERE question='q?'"
        )).fetchone()[0]
        paper_id = conn.execute(text(
            "SELECT id FROM papers WHERE normalized_title='p'"
        )).fetchone()[0]
        packet_id = conn.execute(text(
            "SELECT id FROM dataset_research_packets WHERE source_id='packet-1'"
        )).fetchone()[0]
        conn.execute(text(
            "INSERT INTO question_topics (question_id, topic_id, status, created_at) "
            "VALUES (:q, :t, 'pending', :now)"
        ), {"q": q_id, "t": topic_id, "now": _now()})
        conn.execute(text(
            "INSERT INTO question_concepts (question_id, concept_id, status, created_at) "
            "VALUES (:q, :c, 'confirmed', :now)"
        ), {"q": q_id, "c": concept_id, "now": _now()})
        conn.execute(text("INSERT INTO paper_topics (paper_id, topic_id) VALUES (:p, :t)"),
                     {"p": paper_id, "t": topic_id})
        conn.execute(text("INSERT INTO paper_concepts (paper_id, concept_id) VALUES (:p, :c)"),
                     {"p": paper_id, "c": concept_id})
        conn.execute(
            text("INSERT INTO dataset_packet_topics (packet_id, topic_id) VALUES (:p, :t)"),
            {"p": packet_id, "t": topic_id},
        )
        conn.execute(text("INSERT INTO topic_concepts (topic_id, concept_id) VALUES (:t, :c)"),
                     {"t": topic_id, "c": concept_id})
        conn.execute(text(
            "INSERT INTO study_notes (topic_id, concept_tag, tagged_at) "
            "VALUES (:t, 'topic-tag', :now)"
        ), {"t": topic_id, "now": _now()})
        conn.execute(text(
            "INSERT INTO study_notes (concept_id, concept_tag, tagged_at) "
            "VALUES (:c, 'concept-tag', :now)"
        ), {"c": concept_id, "now": _now()})
        conn.commit()
    return {
        "q_id": q_id,
        "topic_id": topic_id,
        "concept_id": concept_id,
        "paper_id": paper_id,
        "packet_id": packet_id,
    }


def _grouping_id(conn, gtype, name):
    return conn.execute(text(
        "SELECT id FROM groupings WHERE type=:t AND name=:n"
    ), {"t": gtype, "n": name}).fetchone()[0]


def test_backfill_links_all_sources():
    engine = _make_engine()
    ids = _seed_links_fixture(engine)
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        gt = _grouping_id(conn, "topic", "stroke")
        gc = _grouping_id(conn, "concept", "LTP")

        def has(grouping_id, anchor_type, anchor_id, status):
            return conn.execute(
                text(
                    "SELECT 1 FROM grouping_links WHERE grouping_id=:g AND anchor_type=:at "
                    "AND anchor_id=:ai AND status=:s"
                ),
                {"g": grouping_id, "at": anchor_type, "ai": anchor_id, "s": status},
            ).fetchone() is not None

        assert has(gt, "question", ids["q_id"], "pending")
        assert has(gc, "question", ids["q_id"], "confirmed")
        assert has(gt, "paper", ids["paper_id"], "confirmed")
        assert has(gc, "paper", ids["paper_id"], "confirmed")
        assert has(gt, "dataset_packet", ids["packet_id"], "confirmed")
        assert has(gt, "grouping", gc, "confirmed")
        assert conn.execute(text(
            "SELECT COUNT(*) FROM grouping_links WHERE grouping_id=:g AND anchor_type='study_note'"
        ), {"g": gt}).fetchone()[0] == 1
        assert conn.execute(text(
            "SELECT COUNT(*) FROM grouping_links WHERE grouping_id=:g AND anchor_type='study_note'"
        ), {"g": gc}).fetchone()[0] == 1


def test_backfill_links_idempotent():
    engine = _make_engine()
    _seed_links_fixture(engine)
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        before = conn.execute(text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
        after = conn.execute(text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
    assert before == after


def test_full_migration_run_backfills_and_records_version():
    engine = _make_engine()
    _seed_links_fixture(engine)
    apply_migrations(engine, _MIGRATIONS)
    with engine.connect() as conn:
        groupings = conn.execute(text("SELECT COUNT(*) FROM groupings")).fetchone()[0]
        links = conn.execute(text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
    # 2 backfilled by migration 017 (stroke topic + LTP concept) plus the
    # 'plasticity' parent seeded by migration 018 in the full chain = 3.
    assert groupings == 3
    assert links == 8
    assert get_schema_version(engine) >= 17


def test_backfill_skipped_when_legacy_tables_absent():
    """On a fresh DB with no legacy tables, 017 creates the new tables and
    skips the legacy backfill instead of crashing on `FROM topics`."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Deliberately NO Base.metadata.create_all -> legacy tables do not exist.
    with engine.connect() as conn:
        _migration_017_groupings(conn)  # must not raise
        conn.commit()
    with engine.connect() as conn:
        for tbl in ("groupings", "grouping_links"):
            row = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": tbl},
            ).fetchone()
            assert row is not None, f"{tbl} missing"


def test_reapplying_all_migrations_is_noop():
    engine = _make_engine()
    _seed_links_fixture(engine)
    apply_migrations(engine, _MIGRATIONS)
    with engine.connect() as conn:
        g1 = conn.execute(text("SELECT COUNT(*) FROM groupings")).fetchone()[0]
        l1 = conn.execute(text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
    apply_migrations(engine, _MIGRATIONS)
    with engine.connect() as conn:
        g2 = conn.execute(text("SELECT COUNT(*) FROM groupings")).fetchone()[0]
        l2 = conn.execute(text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
    assert (g1, l1) == (g2, l2)
