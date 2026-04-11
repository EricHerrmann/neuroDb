import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from neurodb.connectors.openneuro import OpenNeuroConnector, OpenNeuroDataset

FIXTURE = Path("tests/fixtures/openneuro_sample.json")


def _mock_response():
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_fetch_datasets_returns_two_records():
    conn = OpenNeuroConnector()
    with patch("neurodb.connectors.openneuro.httpx.post", return_value=_mock_response()):
        results = list(conn.fetch_datasets(limit=10))
    assert len(results) == 2
    assert results[0]["id"] == "ds000001"


def test_get_source_id():
    conn = OpenNeuroConnector()
    assert conn.get_source_id({"id": "ds000001"}) == "ds000001"


def test_normalize_dataset_maps_fields():
    conn = OpenNeuroConnector()
    raw = {
        "id": "ds000001",
        "name": "Balloon Analog Risk Task",
        "description": "fMRI study.",
        "metadata": {"modalities": ["MRI"], "numberOfParticipants": 16},
        "doi": "10.18112/openneuro.ds000001.v1.0.0",
    }
    ds = conn.normalize_dataset(raw, index_id=1, run_id=1)
    assert isinstance(ds, OpenNeuroDataset)
    assert ds.source_id == "ds000001"
    assert ds.modality == "MRI"
    assert ds.n_subjects == 16
    assert ds.doi == "10.18112/openneuro.ds000001.v1.0.0"
    assert ds.index_id == 1
