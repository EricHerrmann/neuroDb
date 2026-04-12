from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.schema import DatasetIndex, IngestRun
from neurodb.connectors.openneuro import OpenNeuroDataset
from neurodb.query import search_datasets, get_dataset_by_source_id


def _seed_db(engine):
    with get_session(engine) as session:
        run = IngestRun(source="openneuro", run_at="2026-04-11", version="0.1")
        session.add(run)
        session.flush()

        idx1 = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        idx2 = DatasetIndex(source="openneuro", source_id="ds002", run_id=run.id)
        session.add_all([idx1, idx2])
        session.flush()

        session.add(OpenNeuroDataset(
            index_id=idx1.id, source_id="ds001", title="Plasticity Study",
            modality="fMRI", n_subjects=20, run_id=run.id,
        ))
        session.add(OpenNeuroDataset(
            index_id=idx2.id, source_id="ds002", title="EEG Resting State",
            modality="EEG", n_subjects=15, run_id=run.id,
        ))


def test_search_by_keyword():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_db(engine)
    with get_session(engine) as session:
        results = search_datasets(session, keyword="plasticity")
    assert len(results) == 1
    assert results[0].source_id == "ds001"


def test_search_by_modality():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_db(engine)
    with get_session(engine) as session:
        results = search_datasets(session, modality="EEG")
    assert len(results) == 1
    assert results[0].modality == "EEG"


def test_get_by_source_id():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_db(engine)
    with get_session(engine) as session:
        ds = get_dataset_by_source_id(session, "ds001")
    assert ds.source_id == "ds001"
    assert ds.title == "Plasticity Study"


def test_get_by_source_id_missing_returns_none():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_db(engine)
    with get_session(engine) as session:
        ds = get_dataset_by_source_id(session, "does-not-exist")
    assert ds is None
