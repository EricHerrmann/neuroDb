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
