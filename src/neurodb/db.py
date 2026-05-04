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


_MIGRATIONS: dict[int, callable] = {
    1: _migration_001_study_note_unique,
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
