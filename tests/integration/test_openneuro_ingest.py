import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.provenance import run_ingest
from neurodb.connectors.openneuro import OpenNeuroConnector, OpenNeuroDataset
from neurodb.schema import DatasetIndex, IngestRun

FIXTURE = Path("tests/fixtures/openneuro_sample.json")


def _mock_post(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_full_ingest_stores_datasets():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.openneuro.httpx.post", side_effect=_mock_post):
        run_ingest(engine, connector=OpenNeuroConnector(), limit=10)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 2
        assert session.query(OpenNeuroDataset).count() == 2
        assert session.query(IngestRun).count() == 1
        ds = session.query(OpenNeuroDataset).filter_by(source_id="ds000001").one()
        assert ds.title == "Balloon Analog Risk Task"
        idx = session.query(DatasetIndex).filter_by(source_id="ds000001").one()
        assert idx.source == "openneuro"
