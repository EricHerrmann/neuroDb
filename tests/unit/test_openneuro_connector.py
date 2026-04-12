import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import httpx
import pytest
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


def test_fetch_datasets_raises_on_timeout():
    conn = OpenNeuroConnector()
    with patch(
        "neurodb.connectors.openneuro.httpx.post",
        side_effect=httpx.TimeoutException("timed out"),
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            list(conn.fetch_datasets())


def test_fetch_datasets_raises_on_http_error():
    conn = OpenNeuroConnector()
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    with patch(
        "neurodb.connectors.openneuro.httpx.post",
        side_effect=httpx.HTTPStatusError(
            "400", request=MagicMock(), response=mock_response
        ),
    ):
        with pytest.raises(RuntimeError, match="400"):
            list(conn.fetch_datasets())


def test_fetch_datasets_empty_edges():
    conn = OpenNeuroConnector()
    mock = MagicMock()
    mock.json.return_value = {"data": {"datasets": {"edges": []}}}
    mock.raise_for_status.return_value = None
    with patch("neurodb.connectors.openneuro.httpx.post", return_value=mock):
        results = list(conn.fetch_datasets())
    assert results == []


def test_normalize_dataset_maps_fields():
    conn = OpenNeuroConnector()
    raw = {
        "id": "ds000001",
        "name": "Balloon Analog Risk Task",
        "metadata": {
            "modalities": ["mri"],
            "associatedPaperDOI": "10.18112/openneuro.ds000001.v1.0.0",
            "ages": [21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36],
        },
        "draft": {
            "readme": "fMRI study of risk-taking in healthy adults.",
            "description": {"BIDSVersion": "1.0.0"},
        },
    }
    ds = conn.normalize_dataset(raw, index_id=1, run_id=1)
    assert isinstance(ds, OpenNeuroDataset)
    assert ds.source_id == "ds000001"
    assert ds.modality == "mri"
    assert ds.n_subjects == 16
    assert ds.doi == "10.18112/openneuro.ds000001.v1.0.0"
    assert ds.bids_version == "1.0.0"
    assert ds.description == "fMRI study of risk-taking in healthy adults."
    assert ds.index_id == 1
