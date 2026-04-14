import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.provenance import run_ingest
from neurodb.connectors.dandi import DandiConnector, DandiDataset
from neurodb.schema import DatasetIndex, IngestRun

FIXTURE = Path("tests/fixtures/dandi_api_sample.json")


def _mock_get(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_full_ingest_stores_datasets():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.dandi.httpx.get", side_effect=_mock_get):
        run_ingest(engine, connector=DandiConnector(), limit=10)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 2
        assert session.query(DandiDataset).count() == 2
        assert session.query(IngestRun).count() == 1
        ds = session.query(DandiDataset).filter_by(source_id="000003").one()
        assert ds.title == "Electrophysiology in hippocampus during spatial navigation"
        assert ds.species == "Mus musculus - House mouse"
        assert ds.n_subjects == 5
        assert ds.enriched_at is None
        assert ds.brain_regions is None
        idx = session.query(DatasetIndex).filter_by(source_id="000003").one()
        assert idx.source == "dandi"


def test_double_ingest_does_not_duplicate():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.dandi.httpx.get", side_effect=_mock_get):
        run_ingest(engine, connector=DandiConnector(), limit=10)
        run_ingest(engine, connector=DandiConnector(), limit=10)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 2
        assert session.query(DandiDataset).count() == 2
