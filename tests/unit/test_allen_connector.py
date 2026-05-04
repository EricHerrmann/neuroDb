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


_SAMPLE_DATASET = {
    "id": 999,
    "name": "Mouse Visual Cortex ISH",
    "description": "In situ hybridization study",
    "plane_of_section_id": 1,
    "specimen_id": 42,
    "failed": False,
}


def test_fetch_by_id_returns_raw_dict():
    connector = AllenBrainConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"msg": [_SAMPLE_DATASET]}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.allen_brain.httpx.get", return_value=mock_resp) as mock_get:
        result = connector.fetch_by_id("999")

    assert result == _SAMPLE_DATASET
    call_kwargs = mock_get.call_args[1]
    assert "999" in call_kwargs["params"]["criteria"]


def test_fetch_by_id_raises_if_not_found():
    connector = AllenBrainConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"msg": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.allen_brain.httpx.get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="not found"):
            connector.fetch_by_id("000000")


def test_search_by_keyword_returns_list_of_dicts():
    connector = AllenBrainConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"msg": [_SAMPLE_DATASET]}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.allen_brain.httpx.get", return_value=mock_resp) as mock_get:
        results = connector.search_by_keyword("visual cortex", limit=5)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["id"] == 999
    call_kwargs = mock_get.call_args[1]
    assert "visual cortex" in call_kwargs["params"]["criteria"]
