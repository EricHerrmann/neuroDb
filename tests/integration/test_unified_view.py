from sqlalchemy import create_engine, text
from neurodb.db import init_db, get_session, create_views
from neurodb.schema import CrossRef, DatasetIndex, IngestRun, Subject
from neurodb.connectors.openneuro import OpenNeuroDataset
from neurodb.connectors.allen_brain import AllenDataset
from neurodb.connectors.neurovault import NeuroVaultDataset
from neurodb.connectors.dandi import DandiDataset


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
        idx3 = DatasetIndex(source="neurovault", source_id="1", run_id=run.id)
        session.add(idx3)
        session.flush()
        session.add(NeuroVaultDataset(index_id=idx3.id, source_id="1",
                                      title="Working Memory fMRI", n_subjects=30,
                                      run_id=run.id))
        idx4 = DatasetIndex(source="dandi", source_id="000003", run_id=run.id)
        session.add(idx4)
        session.flush()
        session.add(DandiDataset(index_id=idx4.id, source_id="000003",
                                  title="Ephys in hippocampus", modality="NWB",
                                  n_subjects=5, run_id=run.id))


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
        rows = conn.execute(
            text("SELECT source, modality, n_datasets, total_subjects FROM v_dataset_summary ORDER BY source")
        ).fetchall()
    sources = [r[0] for r in rows]
    assert "openneuro" in sources
    assert "allen_brain" in sources
    row_map = {r[0]: {"modality": r[1], "n_datasets": r[2], "total_subjects": r[3]} for r in rows}
    assert row_map["openneuro"]["n_datasets"] == 1
    assert row_map["allen_brain"]["n_datasets"] == 1
    assert row_map["allen_brain"]["total_subjects"] == 0  # COALESCE ensures 0, not NULL


def test_canonical_subjects_view_filters_by_cross_refs():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    create_views(engine)
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-04-11", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        session.add(idx)
        session.flush()
        # Subject WITH a cross-ref
        subject_with = Subject(index_id=idx.id, source_subject_id="sub-01", age=25.0, sex="M")
        # Second dataset/subject WITHOUT a cross-ref
        idx2 = DatasetIndex(source="openneuro", source_id="ds002", run_id=run.id)
        session.add(idx2)
        session.flush()
        subject_without = Subject(index_id=idx2.id, source_subject_id="sub-99")
        session.add_all([subject_with, subject_without])
        session.flush()
        # Add cross-ref for ds001 only
        cross = CrossRef(source_a="openneuro", id_a="ds001",
                         source_b="allen_brain", id_b="100140756",
                         confidence="high", method="doi_exact")
        session.add(cross)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT source_subject_id FROM v_canonical_subjects")).fetchall()
    subject_ids = [r[0] for r in rows]
    assert "sub-01" in subject_ids
    assert "sub-99" not in subject_ids


def test_unified_view_contains_neurovault():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source")).fetchall()
    sources = {r[0]: r[1] for r in rows}
    assert sources["neurovault"] == 1


def test_unified_view_contains_dandi():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source")).fetchall()
    sources = {r[0]: r[1] for r in rows}
    assert sources["dandi"] == 1
