from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, text
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import Session

from neurodb.schema import Base


def get_engine(url: str = "sqlite:///neurodb.db") -> Engine:
    return _create_engine(url, echo=False)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


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


@contextmanager
def get_session(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine, expire_on_commit=False) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
