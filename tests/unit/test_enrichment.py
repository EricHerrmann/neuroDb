import pandas as pd
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.db import init_db
from neurodb.enrichment import _parse_nwb, run_enrichment


def test_parse_nwb_extracts_electrode_count_sampling_rate_and_version():
    mock_hf = MagicMock()
    mock_hf.__enter__.return_value = mock_hf
    mock_hf.attrs.get.return_value = b"2.3.0"

    mock_nwb = MagicMock()
    mock_nwb.electrodes.__len__.return_value = 64
    mock_nwb.electrodes.to_dataframe.return_value = pd.DataFrame(
        {"sampling_rate": [30000.0] * 64}
    )
    mock_nwb.electrode_groups = {}
    mock_nwb.session_description = "Visual cortex recording"

    mock_io = MagicMock()
    mock_io.__enter__.return_value = mock_io
    mock_io.read.return_value = mock_nwb

    with patch("neurodb.enrichment.h5py.File", return_value=mock_hf), \
         patch("neurodb.enrichment.NWBHDF5IO", return_value=mock_io):
        result = _parse_nwb("/fake/path.nwb")

    assert result["electrode_count"] == 64
    assert result["sampling_rate"] == 30000.0
    assert result["nwb_version"] == "2.3.0"
    assert result["cognitive_paradigm"] == "Visual cortex recording"
    assert result["brain_regions"] is None


def test_parse_nwb_handles_no_electrodes():
    mock_hf = MagicMock()
    mock_hf.__enter__.return_value = mock_hf
    mock_hf.attrs.get.return_value = None

    mock_nwb = MagicMock()
    mock_nwb.electrodes = None
    mock_nwb.electrode_groups = {}
    mock_nwb.session_description = None

    mock_io = MagicMock()
    mock_io.__enter__.return_value = mock_io
    mock_io.read.return_value = mock_nwb

    with patch("neurodb.enrichment.h5py.File", return_value=mock_hf), \
         patch("neurodb.enrichment.NWBHDF5IO", return_value=mock_io):
        result = _parse_nwb("/fake/path.nwb")

    assert result["electrode_count"] is None
    assert result["sampling_rate"] is None
    assert result["nwb_version"] is None
    assert result["cognitive_paradigm"] is None


def test_run_enrichment_returns_zero_when_no_unenriched_records():
    from neurodb.connectors.dandi import DandiDataset  # triggers table registration
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    count = run_enrichment(engine, limit=10)
    assert count == 0


def test_run_enrichment_marks_error_on_download_failure():
    from neurodb.connectors.dandi import DandiDataset
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)

    with Session(engine) as s:
        ds = DandiDataset(
            index_id=1, source_id="000001", title="Test",
            run_id=1, enriched_at=None,
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

    with patch("neurodb.enrichment._download_first_nwb", side_effect=RuntimeError("timeout")):
        count = run_enrichment(engine, limit=1)

    assert count == 0
    with Session(engine) as s:
        rec = s.get(DandiDataset, ds_id)
        assert rec.enriched_at is not None
        assert rec.enriched_at.startswith("ERROR:")


def test_run_enrichment_enriches_record_and_returns_count():
    from neurodb.connectors.dandi import DandiDataset
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)

    with Session(engine) as s:
        ds = DandiDataset(
            index_id=1, source_id="000001", title="Test",
            run_id=1, enriched_at=None,
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

    fake_fields = {
        "electrode_count": 64,
        "sampling_rate": 30000.0,
        "brain_regions": '["V1"]',
        "cognitive_paradigm": "Visual cortex",
        "nwb_version": "2.3.0",
    }

    with patch("neurodb.enrichment._download_first_nwb", return_value="/tmp/fake.nwb"), \
         patch("neurodb.enrichment._parse_nwb", return_value=fake_fields):
        count = run_enrichment(engine, limit=1)

    assert count == 1
    with Session(engine) as s:
        rec = s.get(DandiDataset, ds_id)
        assert rec.electrode_count == 64
        assert rec.sampling_rate == 30000.0
        assert rec.enriched_at is not None
        assert not rec.enriched_at.startswith("ERROR:")
