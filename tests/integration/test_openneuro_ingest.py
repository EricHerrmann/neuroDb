import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.provenance import run_ingest
from neurodb.connectors.openneuro import OpenNeuroConnector, OpenNeuroDataset
from neurodb.schema import DatasetIndex, IngestRun

FIXTURE_SINGLE = Path("tests/fixtures/openneuro_single.json")

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
        assert ds.modality == "mri"
        assert ds.n_subjects == 16
        assert ds.doi == "10.18112/openneuro.ds000001.v1.0.0"
        assert ds.bids_version == "1.0.0"
        assert ds.description == "fMRI study of risk-taking in healthy adults."
        idx = session.query(DatasetIndex).filter_by(source_id="ds000001").one()
        assert idx.source == "openneuro"


def _mock_post_single(*args, **kwargs):
    data = json.loads(FIXTURE_SINGLE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_fetch_by_id_returns_single_dataset():
    connector = OpenNeuroConnector()
    with patch("neurodb.connectors.openneuro.httpx.post", side_effect=_mock_post_single):
        raw = connector.fetch_by_id("ds003685")
    assert raw["id"] == "ds003685"
    assert raw["name"] == "HCP Retinotopy"


def test_fetch_by_id_raises_on_graphql_error():
    error_body = {"errors": [{"message": "Dataset ds003685 has been deleted."}], "data": {"dataset": None}}
    mock = MagicMock()
    mock.json.return_value = error_body
    mock.raise_for_status.return_value = None
    connector = OpenNeuroConnector()
    with patch("neurodb.connectors.openneuro.httpx.post", return_value=mock):
        try:
            connector.fetch_by_id("ds003685")
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "ds003685" in str(e)
            assert "deleted" in str(e)


def test_ingest_by_dataset_id_stores_only_that_dataset():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.openneuro.httpx.post", side_effect=_mock_post_single):
        run_ingest(engine, connector=OpenNeuroConnector(), dataset_ids=["ds003685"])
    with get_session(engine) as session:
        assert session.query(OpenNeuroDataset).count() == 1
        ds = session.query(OpenNeuroDataset).filter_by(source_id="ds003685").one()
        assert ds.title == "HCP Retinotopy"
        assert ds.modality == "mri"


def test_search_by_keyword_returns_matching_datasets():
    connector = OpenNeuroConnector()
    search_body = {
        "data": {
            "datasets": {
                "edges": [
                    {"node": {
                        "id": "ds003787",
                        "name": "NYU Retinotopy Dataset",
                        "metadata": {"species": "Human", "modalities": ["mri"],
                                     "associatedPaperDOI": None, "ages": []},
                        "draft": {"readme": "Population receptive field mapping.",
                                  "description": {"BIDSVersion": "1.4.0"}},
                    }}
                ]
            }
        }
    }
    mock = MagicMock()
    mock.json.return_value = search_body
    mock.raise_for_status.return_value = None
    with patch("neurodb.connectors.openneuro.httpx.post", return_value=mock):
        results = connector.search_by_keyword("retinotopy", limit=5)
    assert len(results) == 1
    assert results[0]["id"] == "ds003787"
    assert results[0]["name"] == "NYU Retinotopy Dataset"
