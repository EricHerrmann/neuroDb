import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import httpx
from neurodb.connectors.dandi import DandiConnector, DandiDataset

FIXTURE = Path(__file__).parent.parent / "fixtures" / "dandi_api_sample.json"


def _mock_get(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_fetch_datasets_returns_two():
    conn = DandiConnector()
    with patch("neurodb.connectors.dandi.httpx.get", side_effect=_mock_get):
        results = list(conn.fetch_datasets(limit=10))
    assert len(results) == 2


def test_get_source_id():
    conn = DandiConnector()
    assert conn.get_source_id({"identifier": "000003"}) == "000003"


def test_normalize_dataset_sets_api_fields():
    conn = DandiConnector()
    data = json.loads(FIXTURE.read_text())
    raw = data["results"][0]
    ds = conn.normalize_dataset(raw, index_id=1, run_id=1)
    assert isinstance(ds, DandiDataset)
    assert ds.source_id == "000003"
    assert ds.title == "Electrophysiology in hippocampus during spatial navigation"
    assert ds.species == "Mus musculus - House mouse"
    assert ds.n_subjects == 5
    assert ds.modality == "NWB: Neurodata Without Borders"
    assert ds.doi is None
    assert ds.enriched_at is None
    assert ds.brain_regions is None
    assert ds.electrode_count is None


def test_normalize_uses_draft_when_no_published_version():
    conn = DandiConnector()
    data = json.loads(FIXTURE.read_text())
    raw = data["results"][1]
    ds = conn.normalize_dataset(raw, index_id=2, run_id=1)
    assert ds.source_id == "000004"
    assert ds.title == "Calcium imaging in visual cortex"
    assert ds.n_subjects == 3


def test_normalize_dataset_handles_missing_asset_summary():
    conn = DandiConnector()
    raw = {
        "identifier": "000099",
        "most_recent_published_version": None,
        "draft_version": {"version": "draft", "name": "Sparse dandiset", "asset_summary": {}},
    }
    ds = conn.normalize_dataset(raw, index_id=3, run_id=1)
    assert ds.source_id == "000099"
    assert ds.species is None
    assert ds.n_subjects is None
    assert ds.modality is None


def test_fetch_datasets_raises_on_timeout():
    conn = DandiConnector()
    with patch(
        "neurodb.connectors.dandi.httpx.get",
        side_effect=httpx.TimeoutException("timed out"),
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            list(conn.fetch_datasets())


_SAMPLE_DANDISET = {
    "identifier": "DANDI:000001",
    "most_recent_published_version": {
        "name": "Test Dandiset",
        "asset_summary": {
            "species": [{"name": "Homo sapiens"}],
            "dataStandard": [{"name": "NWB"}],
            "numberOfSubjects": 5,
        },
    },
}


def test_fetch_by_id_returns_raw_dict():
    connector = DandiConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = _SAMPLE_DANDISET
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.dandi.httpx.get", return_value=mock_resp) as mock_get:
        result = connector.fetch_by_id("DANDI:000001")

    assert result == _SAMPLE_DANDISET
    call_url = mock_get.call_args[0][0]
    assert "000001" in call_url


def test_fetch_by_id_raises_on_http_error():
    connector = DandiConnector()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock(status_code=404, text="not found")
    )
    with patch("neurodb.connectors.dandi.httpx.get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="DANDI API returned"):
            connector.fetch_by_id("DANDI:999999")


def test_search_by_keyword_returns_list_of_dicts():
    connector = DandiConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [_SAMPLE_DANDISET], "next": None}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.dandi.httpx.get", return_value=mock_resp) as mock_get:
        results = connector.search_by_keyword("retinotopy", limit=5)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["identifier"] == "DANDI:000001"
    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["params"]["search"] == "retinotopy"


def test_search_by_keyword_respects_limit():
    connector = DandiConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [_SAMPLE_DANDISET] * 3, "next": None}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.dandi.httpx.get", return_value=mock_resp):
        results = connector.search_by_keyword("plasticity", limit=2)

    assert len(results) <= 2
