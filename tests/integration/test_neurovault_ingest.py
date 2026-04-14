import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.provenance import run_ingest
from neurodb.connectors.neurovault import NeuroVaultConnector, NeuroVaultDataset
from neurodb.schema import DatasetIndex, IngestRun

FIXTURE = Path("tests/fixtures/neurovault_sample.json")


def _mock_get(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_full_ingest_stores_datasets():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.neurovault.httpx.get", side_effect=_mock_get):
        run_ingest(engine, connector=NeuroVaultConnector(), limit=10)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 2
        assert session.query(NeuroVaultDataset).count() == 2
        assert session.query(IngestRun).count() == 1
        ds = session.query(NeuroVaultDataset).filter_by(source_id="1").one()
        assert ds.title == "Working Memory fMRI Study"
        assert ds.doi == "10.1016/j.neuroimage.2021.01.001"
        assert ds.n_images == 42
        assert ds.n_subjects == 30
        assert ds.cognitive_paradigm == "working memory"
        assert ds.tr == 2.0
        idx = session.query(DatasetIndex).filter_by(source_id="1").one()
        assert idx.source == "neurovault"


def test_double_ingest_does_not_duplicate():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.neurovault.httpx.get", side_effect=_mock_get):
        run_ingest(engine, connector=NeuroVaultConnector(), limit=10)
        run_ingest(engine, connector=NeuroVaultConnector(), limit=10)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 2
        assert session.query(NeuroVaultDataset).count() == 2
