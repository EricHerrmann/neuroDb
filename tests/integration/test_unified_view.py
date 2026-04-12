from sqlalchemy import create_engine, text
from neurodb.db import init_db, get_session, create_views
from neurodb.schema import IngestRun, DatasetIndex
from neurodb.connectors.openneuro import OpenNeuroDataset
from neurodb.connectors.allen_brain import AllenDataset


def _seed(engine):
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-04-11", version="0.1")
        session.add(run)
        session.flush()
        idx1 = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        idx2 = DatasetIndex(source="allen_brain", source_id="100140756", run_id=run.id)
        session.add_all([idx1, idx2])
        session.flush()
        session.add(OpenNeuroDataset(index_id=idx1.id, source_id="ds001",
                                     title="fMRI Study", modality="fMRI",
                                     n_subjects=20, run_id=run.id))
        session.add(AllenDataset(index_id=idx2.id, source_id="100140756",
                                  title="ISH Atlas", modality="ISH",
                                  plane_of_section_id=1, run_id=run.id))


def test_unified_view_contains_both_sources():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source")).fetchall()
    sources = {r[0]: r[1] for r in rows}
    assert sources["openneuro"] == 1
    assert sources["allen_brain"] == 1


def test_summary_view_reflects_both_sources():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT source, modality FROM v_dataset_summary ORDER BY source")).fetchall()
    sources = [r[0] for r in rows]
    assert "openneuro" in sources
    assert "allen_brain" in sources
