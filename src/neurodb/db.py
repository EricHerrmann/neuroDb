"""DB epoch — database connection and initialization.

Migration target: src/neurodb/db/connection.py
"""
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import Engine, text
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import Session

from neurodb.migrations import apply_migrations
from neurodb.schema import Base


def get_engine(url: str = "duckdb:///neurodb.duckdb") -> Engine:
    return _create_engine(url, echo=False)


def _migration_001_study_note_unique(conn) -> None:
    """Add unique constraint on (index_id, concept_tag) in study_notes.
    Deletes duplicates first (keeps the row with the lowest id).
    """
    conn.execute(text("""
        DELETE FROM study_notes
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM study_notes
            GROUP BY index_id, concept_tag
        )
    """))
    try:
        conn.execute(text(
            "ALTER TABLE study_notes "
            "ADD CONSTRAINT uq_study_note_index_concept UNIQUE (index_id, concept_tag)"
        ))
    except Exception:
        pass  # constraint already exists on this DB


def _migration_002_model_call_log(conn) -> None:
    """Create model_call_log for existing DB files."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS model_call_log (
            id INTEGER PRIMARY KEY,
            recorded_at VARCHAR(32) NOT NULL,
            task_type VARCHAR(128) NOT NULL,
            provider VARCHAR(64) NOT NULL,
            model VARCHAR(128) NOT NULL,
            mode VARCHAR(64),
            tool_name VARCHAR(128),
            tool_names_json TEXT,
            iteration INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            stop_reason VARCHAR(64),
            elapsed_ms INTEGER,
            estimated_cost_usd FLOAT
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_model_call_log_recorded_at "
        "ON model_call_log (recorded_at)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_model_call_log_task_type "
        "ON model_call_log (task_type)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_model_call_log_model "
        "ON model_call_log (model)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_model_call_log_task_type_model "
        "ON model_call_log (task_type, model)"
    ))


def _migration_003_hypothesis_reviews(conn) -> None:
    """Create hypothesis_reviews for existing DB files."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS hypothesis_reviews (
            id INTEGER PRIMARY KEY,
            hypothesis_id INTEGER NOT NULL,
            created_at VARCHAR(32) NOT NULL,
            model VARCHAR(128) NOT NULL,
            critique_text TEXT NOT NULL,
            unsupported_claims_json TEXT NOT NULL,
            missing_confounds_json TEXT NOT NULL,
            suggested_revisions TEXT NOT NULL,
            status VARCHAR(32) NOT NULL
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_hypothesis_reviews_hypothesis_id "
        "ON hypothesis_reviews (hypothesis_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_hypothesis_reviews_model "
        "ON hypothesis_reviews (model)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_hypothesis_reviews_status "
        "ON hypothesis_reviews (status)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_hypothesis_reviews_hypothesis_status "
        "ON hypothesis_reviews (hypothesis_id, status)"
    ))


def _migration_004_dataset_research_packets(conn) -> None:
    """Create dataset_research_packets for existing DB files."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS dataset_research_packets (
            id INTEGER PRIMARY KEY,
            index_id INTEGER NOT NULL,
            source VARCHAR(64) NOT NULL,
            source_id VARCHAR(128) NOT NULL,
            title TEXT,
            landing_url TEXT,
            api_url TEXT,
            source_summary TEXT,
            doi VARCHAR(256),
            paper_url TEXT,
            publication_title TEXT,
            abstract TEXT,
            authors_json TEXT,
            topics_json TEXT,
            brain_regions_json TEXT,
            diseases_json TEXT,
            modalities_json TEXT,
            participant_summary TEXT,
            methods_json TEXT,
            assets_json TEXT,
            usefulness_state VARCHAR(32) NOT NULL,
            supported_workflows_json TEXT NOT NULL,
            unsupported_workflows_json TEXT NOT NULL,
            missing_context_json TEXT NOT NULL,
            provenance_json TEXT NOT NULL,
            confidence_json TEXT NOT NULL,
            harvested_at VARCHAR(32) NOT NULL,
            run_id INTEGER NOT NULL,
            CONSTRAINT uq_dataset_research_packets_index_id UNIQUE (index_id),
            CONSTRAINT uq_dataset_research_packets_source_id UNIQUE (source, source_id)
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_dataset_research_packets_source "
        "ON dataset_research_packets (source)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_dataset_research_packets_source_id "
        "ON dataset_research_packets (source_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_dataset_research_packets_doi "
        "ON dataset_research_packets (doi)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_dataset_research_packets_usefulness_state "
        "ON dataset_research_packets (usefulness_state)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_dataset_research_packets_source_state "
        "ON dataset_research_packets (source, usefulness_state)"
    ))


def _migration_005_study_notes_topic_id(conn) -> None:
    """Add topic_id column to study_notes for existing DB files that predate the column."""
    try:
        conn.execute(text("ALTER TABLE study_notes ADD COLUMN topic_id INTEGER"))
    except Exception:
        pass  # column already exists
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_study_notes_topic_id ON study_notes (topic_id)"
    ))


def _migration_006_study_notes_concept_paper_id(conn) -> None:
    """Add concept_id and paper_id columns to study_notes (added alongside topic_id in b9791a3)."""
    try:
        conn.execute(text("ALTER TABLE study_notes ADD COLUMN concept_id INTEGER"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE study_notes ADD COLUMN paper_id INTEGER"))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_study_notes_concept_id ON study_notes (concept_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_study_notes_paper_id ON study_notes (paper_id)"
    ))


def _migration_007_research_questions_topic_id(conn) -> None:
    """Add topic_id column to research_questions (added in 7ea2979 to an existing table)."""
    try:
        conn.execute(text("ALTER TABLE research_questions ADD COLUMN topic_id INTEGER"))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_research_questions_topic_id "
        "ON research_questions (topic_id)"
    ))


def _migration_008_evidence_links_status(conn) -> None:
    """Add status column to evidence_links for retract lifecycle."""
    try:
        conn.execute(text("ALTER TABLE evidence_links ADD COLUMN status VARCHAR(16) DEFAULT 'active'"))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_evidence_links_status ON evidence_links (status)"
    ))


def _migration_009_research_questions_archived_guard(conn) -> None:
    """Guard migration: research_questions.status already exists; ensure index present."""
    try:
        conn.execute(text("ALTER TABLE research_questions ADD COLUMN status VARCHAR(32) DEFAULT 'open'"))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_research_questions_status ON research_questions (status)"
    ))


def _migration_010_drop_question_fk_constraints(conn) -> None:
    """Drop FK constraints that prevent updating rows referenced by child tables.

    DuckDB rejects UPDATE on any column of a FK-referenced row, even when
    the updated column is not the FK target. Dropping these constraints
    allows status updates (e.g. archive) while preserving the data linkage.
    """
    for table, constraint in [
        ("research_hypotheses", "research_hypotheses_question_id_id_fkey"),
        ("research_gaps", "research_gaps_question_id_id_fkey"),
        ("research_gaps", "research_gaps_hypothesis_id_id_fkey"),
        ("hypothesis_reviews", "hypothesis_reviews_hypothesis_id_id_fkey"),
    ]:
        try:
            conn.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}"))
        except Exception:
            pass


def _migration_011_drop_hypothesis_reviews_fk(conn) -> None:
    """Drop FK from hypothesis_reviews.hypothesis_id missed by migration 010."""
    try:
        conn.execute(text(
            "ALTER TABLE hypothesis_reviews DROP CONSTRAINT hypothesis_reviews_hypothesis_id_id_fkey"
        ))
    except Exception:
        pass


def _migration_012_rebuild_tables_without_fk(conn) -> None:
    """Rebuild research tables without FK constraints.

    DuckDB blocks UPDATE on any column of a FK-referenced row even when
    the updated column is not the FK target. ALTER TABLE DROP CONSTRAINT
    is also unsupported in DuckDB. The only fix is to drop and recreate
    the affected tables. Data is preserved via CTAS + INSERT INTO SELECT.

    Drop order: children before parents so parent tables can be dropped.
      1. hypothesis_reviews  (FK child of research_hypotheses)
      2. evidence_links       (FK child of research_hypotheses)
      3. research_gaps        (FK child of both)
      4. research_hypotheses  (FK child of research_questions)
    """
    raw = conn.connection.dbapi_connection  # raw duckdb connection
    steps = [
        # --- hypothesis_reviews ---
        "CREATE TABLE hypothesis_reviews_new AS SELECT * FROM hypothesis_reviews",
        "DROP TABLE hypothesis_reviews",
        "ALTER TABLE hypothesis_reviews_new RENAME TO hypothesis_reviews",
        "CREATE INDEX ix_hypothesis_reviews_hypothesis_id ON hypothesis_reviews (hypothesis_id)",
        "CREATE INDEX ix_hypothesis_reviews_hypothesis_status ON hypothesis_reviews (hypothesis_id, status)",
        "CREATE INDEX ix_hypothesis_reviews_model ON hypothesis_reviews (model)",
        "CREATE INDEX ix_hypothesis_reviews_status ON hypothesis_reviews (status)",

        # --- evidence_links ---
        "CREATE TABLE evidence_links_new AS SELECT * FROM evidence_links",
        "DROP TABLE evidence_links",
        "ALTER TABLE evidence_links_new RENAME TO evidence_links",
        "CREATE INDEX ix_evidence_links_claim_id ON evidence_links (claim_id)",
        "CREATE INDEX ix_evidence_links_hypothesis_id ON evidence_links (hypothesis_id)",
        "CREATE INDEX ix_evidence_links_note_id ON evidence_links (note_id)",
        "CREATE INDEX ix_evidence_links_packet_id ON evidence_links (packet_id)",
        "CREATE INDEX ix_evidence_links_paper_id ON evidence_links (paper_id)",
        "CREATE INDEX ix_evidence_links_status ON evidence_links (status)",

        # --- research_gaps ---
        "CREATE TABLE research_gaps_new AS SELECT * FROM research_gaps",
        "DROP TABLE research_gaps",
        "ALTER TABLE research_gaps_new RENAME TO research_gaps",

        # --- research_hypotheses ---
        "CREATE TABLE research_hypotheses_new AS SELECT * FROM research_hypotheses",
        "DROP TABLE research_hypotheses",
        "ALTER TABLE research_hypotheses_new RENAME TO research_hypotheses",
        "CREATE INDEX ix_research_hypotheses_status ON research_hypotheses (status)",
    ]
    for sql in steps:
        raw.execute(sql)


def _migration_013_system_warnings(conn) -> None:
    """Create system_warnings for provider routing and operational warnings."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS system_warnings (
            id INTEGER PRIMARY KEY,
            recorded_at VARCHAR(32) NOT NULL,
            warning_type VARCHAR(32) NOT NULL,
            severity VARCHAR(8) NOT NULL,
            task_type VARCHAR(128) NOT NULL,
            requested_provider VARCHAR(64),
            selected_provider VARCHAR(64),
            message TEXT NOT NULL
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_system_warnings_recorded_at "
        "ON system_warnings (recorded_at)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_system_warnings_warning_type "
        "ON system_warnings (warning_type)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_system_warnings_severity "
        "ON system_warnings (severity)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_system_warnings_task_type "
        "ON system_warnings (task_type)"
    ))


def _migration_014_chat_session_topic_category(conn) -> None:
    """Add topic_category to chat_sessions for LLM-assigned grouping."""
    try:
        conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN topic_category VARCHAR(64)"))
    except Exception:
        pass  # column already exists


def _migration_015_model_call_log_context_counts(conn) -> None:
    """Add retrieval telemetry columns to model_call_log."""
    for col in (
        "context_papers_count",
        "context_notes_count",
        "context_claims_count",
        "context_datasets_count",
        "context_gap_count",
    ):
        try:
            conn.execute(text(f"ALTER TABLE model_call_log ADD COLUMN {col} INTEGER"))
        except Exception:
            pass  # column already exists


def _migration_016_question_topic_tables(conn) -> None:
    """Create question_topics and question_concepts join tables; add origin_session_id to research_questions."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS question_topics (
            id INTEGER PRIMARY KEY,
            question_id INTEGER NOT NULL,
            topic_id INTEGER NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at VARCHAR(32) NOT NULL
        )
    """))
    try:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_question_topic "
            "ON question_topics (question_id, topic_id)"
        ))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_question_topics_question_id "
        "ON question_topics (question_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_question_topics_status "
        "ON question_topics (status)"
    ))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS question_concepts (
            id INTEGER PRIMARY KEY,
            question_id INTEGER NOT NULL,
            concept_id INTEGER NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at VARCHAR(32) NOT NULL
        )
    """))
    try:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_question_concept "
            "ON question_concepts (question_id, concept_id)"
        ))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_question_concepts_question_id "
        "ON question_concepts (question_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_question_concepts_status "
        "ON question_concepts (status)"
    ))

    try:
        conn.execute(text("ALTER TABLE research_questions ADD COLUMN origin_session_id INTEGER"))
    except Exception:
        pass  # column already exists

    # Backfill question_topics from existing non-null topic_id rows
    try:
        conn.execute(text("""
            INSERT INTO question_topics (question_id, topic_id, status, created_at)
            SELECT id, topic_id, 'confirmed', created_at
            FROM research_questions
            WHERE topic_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM question_topics qt
                WHERE qt.question_id = research_questions.id
                  AND qt.topic_id = research_questions.topic_id
              )
        """))
    except Exception:
        pass  # backfill already applied or table was empty


def _migration_017_groupings(conn) -> None:
    """Create unified groupings/grouping_links tables and backfill legacy rows."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS groupings (
            id INTEGER PRIMARY KEY,
            type VARCHAR(32) NOT NULL,
            name VARCHAR(256) NOT NULL,
            parent_id INTEGER,
            status VARCHAR(16) NOT NULL DEFAULT 'active',
            description TEXT,
            created_at VARCHAR(32) NOT NULL,
            updated_at VARCHAR(32) NOT NULL
        )
    """))
    try:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_groupings_type_name ON groupings (type, name)"
        ))
    except Exception:
        pass
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_groupings_type ON groupings (type)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_groupings_parent_id ON groupings (parent_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_groupings_status ON groupings (status)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS grouping_links (
            id INTEGER PRIMARY KEY,
            grouping_id INTEGER NOT NULL,
            anchor_type VARCHAR(32) NOT NULL,
            anchor_id INTEGER NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'confirmed',
            created_at VARCHAR(32) NOT NULL
        )
    """))
    try:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_grouping_links_anchor "
            "ON grouping_links (grouping_id, anchor_type, anchor_id)"
        ))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_grouping_links_grouping_id "
        "ON grouping_links (grouping_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_grouping_links_anchor "
        "ON grouping_links (anchor_type, anchor_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_grouping_links_status ON grouping_links (status)"
    ))

    conn.execute(text("""
        INSERT INTO groupings (
            id, type, name, parent_id, status, description, created_at, updated_at
        )
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM groupings)
                + ROW_NUMBER() OVER (ORDER BY t.id),
            'topic',
            t.name,
            NULL,
            t.status,
            t.description,
            t.created_at,
            t.updated_at
        FROM topics t
        WHERE NOT EXISTS (
            SELECT 1 FROM groupings g WHERE g.type = 'topic' AND g.name = t.name
        )
    """))
    conn.execute(text("""
        INSERT INTO groupings (
            id, type, name, parent_id, status, description, created_at, updated_at
        )
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM groupings)
                + ROW_NUMBER() OVER (ORDER BY c.id),
            'concept',
            c.name,
            NULL,
            c.status,
            c.description,
            c.created_at,
            c.updated_at
        FROM concepts c
        WHERE NOT EXISTS (
            SELECT 1 FROM groupings g WHERE g.type = 'concept' AND g.name = c.name
        )
    """))

    now_iso = datetime.now(UTC).isoformat()

    conn.execute(text("""
        INSERT INTO grouping_links (id, grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM grouping_links)
                + ROW_NUMBER() OVER (ORDER BY qt.question_id, qt.topic_id),
            g.id,
            'question',
            qt.question_id,
            qt.status,
            :now
        FROM question_topics qt
        JOIN topics t ON t.id = qt.topic_id
        JOIN groupings g ON g.type = 'topic' AND g.name = t.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id
              AND gl.anchor_type = 'question'
              AND gl.anchor_id = qt.question_id
        )
    """), {"now": now_iso})

    conn.execute(text("""
        INSERT INTO grouping_links (id, grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM grouping_links)
                + ROW_NUMBER() OVER (ORDER BY qc.question_id, qc.concept_id),
            g.id,
            'question',
            qc.question_id,
            qc.status,
            :now
        FROM question_concepts qc
        JOIN concepts c ON c.id = qc.concept_id
        JOIN groupings g ON g.type = 'concept' AND g.name = c.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id
              AND gl.anchor_type = 'question'
              AND gl.anchor_id = qc.question_id
        )
    """), {"now": now_iso})

    conn.execute(text("""
        INSERT INTO grouping_links (id, grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM grouping_links)
                + ROW_NUMBER() OVER (ORDER BY pt.paper_id, pt.topic_id),
            g.id,
            'paper',
            pt.paper_id,
            'confirmed',
            :now
        FROM paper_topics pt
        JOIN topics t ON t.id = pt.topic_id
        JOIN groupings g ON g.type = 'topic' AND g.name = t.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id
              AND gl.anchor_type = 'paper'
              AND gl.anchor_id = pt.paper_id
        )
    """), {"now": now_iso})

    conn.execute(text("""
        INSERT INTO grouping_links (id, grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM grouping_links)
                + ROW_NUMBER() OVER (ORDER BY pc.paper_id, pc.concept_id),
            g.id,
            'paper',
            pc.paper_id,
            'confirmed',
            :now
        FROM paper_concepts pc
        JOIN concepts c ON c.id = pc.concept_id
        JOIN groupings g ON g.type = 'concept' AND g.name = c.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id
              AND gl.anchor_type = 'paper'
              AND gl.anchor_id = pc.paper_id
        )
    """), {"now": now_iso})

    conn.execute(text("""
        INSERT INTO grouping_links (id, grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM grouping_links)
                + ROW_NUMBER() OVER (ORDER BY dpt.packet_id, dpt.topic_id),
            g.id,
            'dataset_packet',
            dpt.packet_id,
            'confirmed',
            :now
        FROM dataset_packet_topics dpt
        JOIN topics t ON t.id = dpt.topic_id
        JOIN groupings g ON g.type = 'topic' AND g.name = t.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id
              AND gl.anchor_type = 'dataset_packet'
              AND gl.anchor_id = dpt.packet_id
        )
    """), {"now": now_iso})

    conn.execute(text("""
        INSERT INTO grouping_links (id, grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM grouping_links)
                + ROW_NUMBER() OVER (ORDER BY tc.topic_id, tc.concept_id),
            gt.id,
            'grouping',
            gc.id,
            'confirmed',
            :now
        FROM topic_concepts tc
        JOIN topics t ON t.id = tc.topic_id
        JOIN concepts c ON c.id = tc.concept_id
        JOIN groupings gt ON gt.type = 'topic' AND gt.name = t.name
        JOIN groupings gc ON gc.type = 'concept' AND gc.name = c.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = gt.id
              AND gl.anchor_type = 'grouping'
              AND gl.anchor_id = gc.id
        )
    """), {"now": now_iso})

    conn.execute(text("""
        INSERT INTO grouping_links (id, grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM grouping_links)
                + ROW_NUMBER() OVER (ORDER BY sn.id),
            g.id,
            'study_note',
            sn.id,
            'confirmed',
            :now
        FROM study_notes sn
        JOIN topics t ON t.id = sn.topic_id
        JOIN groupings g ON g.type = 'topic' AND g.name = t.name
        WHERE sn.topic_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id
              AND gl.anchor_type = 'study_note'
              AND gl.anchor_id = sn.id
        )
    """), {"now": now_iso})

    conn.execute(text("""
        INSERT INTO grouping_links (id, grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM grouping_links)
                + ROW_NUMBER() OVER (ORDER BY sn.id),
            g.id,
            'study_note',
            sn.id,
            'confirmed',
            :now
        FROM study_notes sn
        JOIN concepts c ON c.id = sn.concept_id
        JOIN groupings g ON g.type = 'concept' AND g.name = c.name
        WHERE sn.concept_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id
              AND gl.anchor_type = 'study_note'
              AND gl.anchor_id = sn.id
        )
    """), {"now": now_iso})


def _migration_018_seed_grouping_hierarchy(conn) -> None:
    """Seed the plasticity/stroke topic hierarchy on the unified groupings table.
    Creates a top-level 'plasticity' topic and sets parent_id on seed children.
    Additive and idempotent."""
    now = datetime.now(UTC).isoformat()
    conn.execute(text("""
        INSERT INTO groupings (id, type, name, parent_id, status, description, created_at, updated_at)
        SELECT
            (SELECT COALESCE(MAX(id), 0) FROM groupings) + 1,
            'topic', 'plasticity', NULL, 'active', NULL, :now, :now
        WHERE NOT EXISTS (
            SELECT 1 FROM groupings WHERE type='topic' AND name='plasticity'
        )
    """), {"now": now})

    seed = {
        "plasticity": [
            "neuroplasticity", "circuit plasticity", "interhemispheric plasticity",
            "cortical remapping", "maladaptive reorganization",
            "interhemispheric competition", "interhemispheric inhibition",
            "transcallosal inhibition",
        ],
        "stroke": [
            "stroke recovery", "stroke rehabilitation", "stroke severity",
            "peri-infarct cortex",
        ],
    }
    for parent_name, children in seed.items():
        prow = conn.execute(text(
            "SELECT id FROM groupings WHERE type='topic' AND name=:n"
        ), {"n": parent_name}).fetchone()
        if prow is None:
            continue
        pid = prow[0]
        for child in children:
            conn.execute(text("""
                UPDATE groupings SET parent_id = :pid, updated_at = :now
                WHERE type='topic' AND name = :child
                  AND (parent_id IS NULL OR parent_id <> :pid)
            """), {"pid": pid, "now": now, "child": child})


def _migration_019_resync_grouping_sequences(conn) -> None:
    """Advance the groupings / grouping_links id sequences past the max backfilled id.

    Migrations 017/018 insert rows with explicit ids (COALESCE(MAX(id),0)+1), which
    does NOT advance the DuckDB sequence used by the ORM insert path (nextval). Without
    this, the first agent-proposed grouping/link collides on the primary key. DuckDB
    only; SQLite uses autoincrement and needs no resync.
    """
    if conn.dialect.name != "duckdb":
        return
    for table, seq in (
        ("groupings", "groupings_id_seq"),
        ("grouping_links", "grouping_links_id_seq"),
    ):
        max_id = conn.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table}")).scalar() or 0
        conn.execute(text(f"CREATE OR REPLACE SEQUENCE {seq} START WITH {int(max_id) + 1}"))


_MIGRATIONS: dict[int, callable] = {
    1: _migration_001_study_note_unique,
    2: _migration_002_model_call_log,
    3: _migration_003_hypothesis_reviews,
    4: _migration_004_dataset_research_packets,
    5: _migration_005_study_notes_topic_id,
    6: _migration_006_study_notes_concept_paper_id,
    7: _migration_007_research_questions_topic_id,
    8: _migration_008_evidence_links_status,
    9: _migration_009_research_questions_archived_guard,
    10: _migration_010_drop_question_fk_constraints,
    11: _migration_011_drop_hypothesis_reviews_fk,
    12: _migration_012_rebuild_tables_without_fk,
    13: _migration_013_system_warnings,
    14: _migration_014_chat_session_topic_category,
    15: _migration_015_model_call_log_context_counts,
    16: _migration_016_question_topic_tables,
    17: _migration_017_groupings,
    18: _migration_018_seed_grouping_hierarchy,
    19: _migration_019_resync_grouping_sequences,
}


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    seed_learning_sources(engine)
    apply_migrations(engine, _MIGRATIONS)


def seed_learning_sources(engine: Engine) -> None:
    """Seed learning_sources with the chapter registry. Idempotent — skips existing rows."""
    import json
    from datetime import datetime, timezone
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from neurodb.schema import LearningSource
    from neurodb.chapter_registry import REGISTRY

    with Session(engine) as session:
        for book_key, book in REGISTRY.items():
            existing = session.execute(
                select(LearningSource).where(LearningSource.source_key == book_key)
            ).scalar_one_or_none()
            if existing is not None:
                continue
            session.add(LearningSource(
                source_type="book",
                source_key=book_key,
                display_name=book["display_name"],
                content_json=json.dumps({
                    "chapters": {
                        str(ch_num): ch_data
                        for ch_num, ch_data in book["chapters"].items()
                    }
                }),
                metadata_json=None,
                added_by="seed",
                added_at=datetime.now(timezone.utc).isoformat(),
            ))
        session.commit()


def create_views(engine: Engine) -> None:
    """Create unified SQL views across source-specific tables (Approach C).

    Each new source connector added in future phases must add its own
    SELECT branch to v_all_datasets and re-run create_views.

    Views are dropped and re-created unconditionally so stale definitions
    never survive a re-run. Drop order is reverse dependency order.
    """
    with engine.connect() as conn:
        # Drop in reverse dependency order so dependent views go first.
        conn.execute(text("DROP VIEW IF EXISTS v_canonical_subjects"))
        conn.execute(text("DROP VIEW IF EXISTS v_dataset_summary"))
        conn.execute(text("DROP VIEW IF EXISTS v_all_datasets"))

        conn.execute(text("""
            CREATE VIEW v_all_datasets AS
            SELECT
                di.id        AS index_id,
                di.source,
                di.source_id,
                od.title,
                od.doi,
                od.modality,
                od.n_subjects,
                od.description,
                di.run_id
            FROM datasets_index di
            JOIN openneuro_datasets od ON od.index_id = di.id
            WHERE di.source = 'openneuro'
            UNION ALL
            SELECT
                di.id        AS index_id,
                di.source,
                di.source_id,
                ad.title,
                NULL         AS doi,
                ad.modality,
                NULL         AS n_subjects,
                ad.description,
                di.run_id
            FROM datasets_index di
            JOIN allen_datasets ad ON ad.index_id = di.id
            WHERE di.source = 'allen_brain'
            UNION ALL
            SELECT
                di.id        AS index_id,
                di.source,
                di.source_id,
                nv.title,
                nv.doi,
                'fMRI'       AS modality,
                nv.n_subjects,
                nv.description,
                di.run_id
            FROM datasets_index di
            JOIN neurovault_datasets nv ON nv.index_id = di.id
            WHERE di.source = 'neurovault'
            UNION ALL
            SELECT
                di.id        AS index_id,
                di.source,
                di.source_id,
                dd.title,
                dd.doi,
                dd.modality,
                dd.n_subjects,
                dd.cognitive_paradigm AS description,
                di.run_id
            FROM datasets_index di
            JOIN dandi_datasets dd ON dd.index_id = di.id
            WHERE di.source = 'dandi'
        """))
        conn.execute(text("""
            CREATE VIEW v_dataset_summary AS
            SELECT
                source,
                modality,
                COUNT(*)                    AS n_datasets,
                SUM(COALESCE(n_subjects, 0)) AS total_subjects
            FROM v_all_datasets
            GROUP BY source, modality
        """))
        conn.execute(text("""
            CREATE VIEW v_canonical_subjects AS
            SELECT
                s.id,
                s.index_id,
                s.source_subject_id,
                s.age,
                s.sex,
                s.diagnosis,
                s.metadata_json,
                di.source,
                di.source_id
            FROM subjects s
            JOIN datasets_index di ON di.id = s.index_id
            WHERE EXISTS (
                SELECT 1 FROM cross_refs cr
                WHERE (cr.source_a = di.source AND cr.id_a = di.source_id)
                   OR (cr.source_b = di.source AND cr.id_b = di.source_id)
            )
        """))
        conn.commit()  # DuckDB DDL is transactional; commit so views survive outside this block


@contextmanager
def get_session(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine, expire_on_commit=False) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
