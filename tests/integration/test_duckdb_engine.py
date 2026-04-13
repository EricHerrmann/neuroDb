"""Integration tests proving the full stack works with a DuckDB engine.

All existing unit tests continue to use sqlite:///:memory:. These tests
prove DuckDB compatibility without touching the existing test suite.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from neurodb.db import init_db, create_views, get_session
from neurodb.schema import DatasetIndex, IngestRun
from neurodb.connectors.openneuro import OpenNeuroDataset
from neurodb.connectors.allen_brain import AllenDataset


def _make_engine():
    # StaticPool ensures all engine.connect() calls share the same underlying
    # DuckDB connection, so DDL (views, tables) created in one block is visible
    # in the next — critical for DuckDB in-memory which is per-connection.
    return create_engine("duckdb:///:memory:", poolclass=StaticPool)


def _seed(engine):
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-04-13", version="0.1")
        session.add(run)
        session.flush()
        idx1 = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        idx2 = DatasetIndex(source="allen_brain", source_id="a001", run_id=run.id)
        session.add_all([idx1, idx2])
        session.flush()
        session.add(OpenNeuroDataset(
            index_id=idx1.id, source_id="ds001", title="fMRI Study",
            modality="fMRI", n_subjects=20, run_id=run.id,
        ))
        session.add(AllenDataset(
            index_id=idx2.id, source_id="a001", title="ISH Atlas",
            modality="ISH", plane_of_section_id=1, run_id=run.id,
        ))


def test_init_db_creates_tables():
    engine = _make_engine()
    init_db(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SHOW TABLES")).fetchall()
    table_names = {r[0] for r in rows}
    assert "datasets_index" in table_names
    assert "ingest_runs" in table_names
    assert "openneuro_datasets" in table_names
    assert "allen_datasets" in table_names


def test_create_views_is_queryable():
    engine = _make_engine()
    init_db(engine)
    create_views(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM v_all_datasets LIMIT 1")).fetchall()
    assert rows == []  # empty but no error


def test_orm_insert_and_query():
    engine = _make_engine()
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source ORDER BY source")
        ).fetchall()
    sources = {r[0]: r[1] for r in rows}
    assert sources["openneuro"] == 1
    assert sources["allen_brain"] == 1


def test_summary_view_with_duckdb():
    engine = _make_engine()
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT source, modality, n_datasets FROM v_dataset_summary ORDER BY source")
        ).fetchall()
    sources = [r[0] for r in rows]
    assert "openneuro" in sources
    assert "allen_brain" in sources


def test_keyword_search_via_view():
    engine = _make_engine()
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT source_id FROM v_all_datasets WHERE LOWER(title) LIKE '%fmri%'")
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "ds001"


def test_idempotent_create_views():
    """create_views can be called twice without error (drop+recreate)."""
    engine = _make_engine()
    init_db(engine)
    create_views(engine)
    create_views(engine)  # second call must not raise
