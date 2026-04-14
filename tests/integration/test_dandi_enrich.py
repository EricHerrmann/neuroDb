import json
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.connectors.dandi import DandiDataset  # noqa: F401 — registers model with Base
from neurodb.enrichment import run_enrichment
from neurodb.schema import DatasetIndex, IngestRun

NWB_FIXTURE = Path("tests/fixtures/dandi_sample.nwb")


def _seed_one(engine, source_id: str = "000003", enriched_at=None):
    with get_session(engine) as session:
        run = IngestRun(source="dandi", run_at="2026-04-13T00:00:00Z", version="0.1.0")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="dandi", source_id=source_id, run_id=run.id)
        session.add(idx)
        session.flush()
        ds = DandiDataset(
            index_id=idx.id,
            source_id=source_id,
            title="Test Dandiset",
            enriched_at=enriched_at,
            run_id=run.id,
        )
        session.add(ds)


def test_enrichment_populates_nwb_fields():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_one(engine)

    with patch("neurodb.enrichment._download_first_nwb", return_value=str(NWB_FIXTURE)):
        count = run_enrichment(engine)

    assert count == 1
    with get_session(engine) as session:
        rec = session.query(DandiDataset).filter_by(source_id="000003").one()
        assert rec.enriched_at is not None
        assert not rec.enriched_at.startswith("ERROR")
        assert rec.electrode_count == 1
        assert rec.sampling_rate == 30000.0
        brain = json.loads(rec.brain_regions)
        assert "CA1" in brain
        assert rec.cognitive_paradigm == "Motor cortex recording during lever pressing task"


def test_enrichment_skips_already_enriched():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_one(engine, enriched_at="2026-04-13T00:00:00+00:00")

    with patch("neurodb.enrichment._download_first_nwb") as mock_dl:
        count = run_enrichment(engine)

    assert count == 0
    mock_dl.assert_not_called()


def test_enrichment_with_limit():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_one(engine, source_id="000003")
    _seed_one(engine, source_id="000004")

    with patch("neurodb.enrichment._download_first_nwb", return_value=str(NWB_FIXTURE)):
        count = run_enrichment(engine, limit=1)

    assert count == 1


def test_enrichment_handles_parse_error():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_one(engine)

    # Return a path that does not exist — _parse_nwb will raise, enriched_at set to ERROR:...
    with patch("neurodb.enrichment._download_first_nwb", return_value="/nonexistent/path.nwb"):
        count = run_enrichment(engine)

    assert count == 0
    with get_session(engine) as session:
        rec = session.query(DandiDataset).filter_by(source_id="000003").one()
        assert rec.enriched_at is not None
        assert rec.enriched_at.startswith("ERROR")
