from typing import Iterator
from sqlalchemy import Integer, String, ForeignKey, Sequence, create_engine, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from neurodb.schema import Base, DatasetIndex, DatasetResearchPacket, IngestRun
from neurodb.connectors.base import BaseConnector
from neurodb.db import init_db
from neurodb.provenance import run_ingest


class FakeDataset(Base):
    """Minimal source-specific table for provenance test isolation."""
    __tablename__ = "fake_datasets"

    id: Mapped[int] = mapped_column(Integer, Sequence("fake_datasets_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False, unique=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)


class FakeConnector(BaseConnector):
    SOURCE_NAME = "fake"
    VERSION = "0.0.1"

    def __init__(self, datasets: list[dict]):
        self._datasets = datasets

    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        return iter(self._datasets[:limit])

    def get_source_id(self, raw: dict) -> str:
        return raw["id"]

    def normalize_dataset(self, raw: dict, index_id: int, run_id: int) -> FakeDataset:
        return FakeDataset(index_id=index_id, source_id=raw["id"], run_id=run_id)

    def fetch_subjects(self, dataset_source_id: str) -> Iterator[dict]:
        return iter([])

    def normalize_subject(self, raw: dict, index_id: int):
        pass

    def fetch_by_id(self, dataset_id: str) -> dict:
        for d in self._datasets:
            if d["id"] == dataset_id:
                return d
        raise RuntimeError(f"fake: {dataset_id} not found")


def _engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return engine


def test_run_ingest_returns_ingest_run_with_correct_metadata():
    engine = _engine()
    connector = FakeConnector([])  # no datasets — just verify IngestRun creation
    run = run_ingest(engine, connector)
    assert isinstance(run, IngestRun)
    assert run.source == "fake"
    assert run.version == "0.0.1"
    assert run.id is not None


def test_run_ingest_creates_dataset_index_row():
    engine = _engine()
    connector = FakeConnector([{"id": "ds001"}])
    run_ingest(engine, connector)

    with Session(engine) as s:
        rows = s.execute(
            select(DatasetIndex).where(DatasetIndex.source == "fake")
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].source_id == "ds001"


def test_run_ingest_is_idempotent():
    engine = _engine()
    connector = FakeConnector([{"id": "ds001"}])

    run_ingest(engine, connector)
    run_ingest(engine, connector)

    with Session(engine) as s:
        rows = s.execute(
            select(DatasetIndex).where(DatasetIndex.source == "fake")
        ).scalars().all()
        packets = s.execute(
            select(DatasetResearchPacket).where(DatasetResearchPacket.source == "fake")
        ).scalars().all()

    assert len(rows) == 1  # no duplicate DatasetIndex row on second run
    assert len(packets) == 1  # no duplicate research packet row on second run


def test_run_ingest_dataset_ids_uses_fetch_by_id_not_fetch_datasets():
    engine = _engine()
    connector = FakeConnector([{"id": "ds001"}, {"id": "ds002"}])

    fetch_datasets_calls = []
    fetch_by_id_calls = []
    original_fetch_datasets = connector.fetch_datasets
    original_fetch_by_id = connector.fetch_by_id

    def tracking_fetch_datasets(limit=100):
        fetch_datasets_calls.append(True)
        return original_fetch_datasets(limit)

    def tracking_fetch_by_id(dataset_id):
        fetch_by_id_calls.append(dataset_id)
        return original_fetch_by_id(dataset_id)

    connector.fetch_datasets = tracking_fetch_datasets
    connector.fetch_by_id = tracking_fetch_by_id

    run_ingest(engine, connector, dataset_ids=["ds002"])

    assert fetch_by_id_calls == ["ds002"]
    assert fetch_datasets_calls == []

    with Session(engine) as s:
        rows = s.execute(
            select(DatasetIndex).where(DatasetIndex.source == "fake")
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].source_id == "ds002"
