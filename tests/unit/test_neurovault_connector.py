import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import httpx
from neurodb.connectors.neurovault import NeuroVaultConnector, NeuroVaultDataset

FIXTURE = Path(__file__).parent.parent / "fixtures" / "neurovault_sample.json"


def _mock_get(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_fetch_datasets_returns_two():
    conn = NeuroVaultConnector()
    with patch("neurodb.connectors.neurovault.httpx.get", side_effect=_mock_get):
        results = list(conn.fetch_datasets(limit=10))
    assert len(results) == 2


def test_get_source_id():
    conn = NeuroVaultConnector()
    assert conn.get_source_id({"id": 1}) == "1"


def test_normalize_dataset_maps_all_fields():
    conn = NeuroVaultConnector()
    data = json.loads(FIXTURE.read_text())
    raw = data["results"][0]
    ds = conn.normalize_dataset(raw, index_id=1, run_id=1)
    assert isinstance(ds, NeuroVaultDataset)
    assert ds.source_id == "1"
    assert ds.title == "Working Memory fMRI Study"
    assert ds.doi == "10.1016/j.neuroimage.2021.01.001"
    assert ds.n_images == 42
    assert ds.n_subjects == 30
    assert ds.cognitive_paradigm == "working memory"
    assert ds.tr == 2.0
    assert ds.resolution == "2mm"
    assert ds.index_id == 1
    assert json.loads(ds.metadata_json)["id"] == 1


def test_normalize_dataset_handles_null_fields():
    conn = NeuroVaultConnector()
    data = json.loads(FIXTURE.read_text())
    raw = data["results"][1]
    ds = conn.normalize_dataset(raw, index_id=2, run_id=1)
    assert ds.doi is None
    assert ds.n_subjects is None
    assert ds.cognitive_paradigm is None
    assert ds.resolution is None


def test_fetch_datasets_raises_on_timeout():
    conn = NeuroVaultConnector()
    with patch(
        "neurodb.connectors.neurovault.httpx.get",
        side_effect=httpx.TimeoutException("timed out"),
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            list(conn.fetch_datasets())


def test_fetch_datasets_raises_on_http_error():
    conn = NeuroVaultConnector()
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = "Service Unavailable"
    with patch(
        "neurodb.connectors.neurovault.httpx.get",
        side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=mock_response),
    ):
        with pytest.raises(RuntimeError, match="503"):
            list(conn.fetch_datasets())


_SAMPLE_COLLECTION = {
    "id": 1234,
    "name": "Retinotopy Study",
    "description": "Visual cortex retinotopy",
    "doi": None,
    "number_of_images": 10,
    "number_of_subjects": 8,
}


def test_fetch_by_id_returns_raw_dict():
    connector = NeuroVaultConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = _SAMPLE_COLLECTION
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.neurovault.httpx.get", return_value=mock_resp) as mock_get:
        result = connector.fetch_by_id("1234")

    assert result == _SAMPLE_COLLECTION
    call_url = mock_get.call_args[0][0]
    assert "1234" in call_url


def test_fetch_by_id_raises_on_http_error():
    connector = NeuroVaultConnector()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock(status_code=404, text="not found")
    )
    with patch("neurodb.connectors.neurovault.httpx.get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="NeuroVault API returned"):
            connector.fetch_by_id("999999")


def test_search_by_keyword_returns_list_of_dicts():
    connector = NeuroVaultConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [_SAMPLE_COLLECTION], "next": None}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.neurovault.httpx.get", return_value=mock_resp) as mock_get:
        results = connector.search_by_keyword("retinotopy", limit=5)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["name"] == "Retinotopy Study"
    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["params"]["search"] == "retinotopy"
