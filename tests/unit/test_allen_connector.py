import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import httpx
import pytest
from neurodb.connectors.allen_brain import AllenBrainConnector, AllenDataset

FIXTURE = Path(__file__).parent.parent / "fixtures" / "allen_sample.json"


def _mock_get(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_fetch_datasets_returns_two():
    conn = AllenBrainConnector()
    with patch("neurodb.connectors.allen_brain.httpx.get", side_effect=_mock_get):
        results = list(conn.fetch_datasets(limit=10))
    assert len(results) == 2


def test_get_source_id():
    conn = AllenBrainConnector()
    assert conn.get_source_id({"id": 100140756}) == "100140756"


def test_fetch_datasets_raises_on_timeout():
    conn = AllenBrainConnector()
    with patch(
        "neurodb.connectors.allen_brain.httpx.get",
        side_effect=httpx.TimeoutException("timed out"),
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            list(conn.fetch_datasets())


def test_fetch_datasets_raises_on_http_error():
    conn = AllenBrainConnector()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    with patch(
        "neurodb.connectors.allen_brain.httpx.get",
        side_effect=httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_response
        ),
    ):
        with pytest.raises(RuntimeError, match="500"):
            list(conn.fetch_datasets())


def test_normalize_dataset_sets_fields():
    conn = AllenBrainConnector()
    raw = {"id": 100140756, "name": "Mouse Brain Atlas", "description": "ISH atlas", "plane_of_section_id": 1}
    ds = conn.normalize_dataset(raw, index_id=1, run_id=1)
    assert isinstance(ds, AllenDataset)
    assert ds.source_id == "100140756"
    assert ds.modality == "ISH"
    assert ds.plane_of_section_id == 1
    assert ds.index_id == 1
