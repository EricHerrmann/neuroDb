"""DB epoch — database connection and initialization.

Migration target: src/neurodb/db/connection.py
"""
from collections.abc import Generator
from contextlib import contextmanager

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
