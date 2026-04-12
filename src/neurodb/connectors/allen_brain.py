import json
from typing import Any, Iterator
import httpx
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from neurodb.schema import Base, Subject
from neurodb.connectors.base import BaseConnector

_BASE = "https://api.brain-map.org/api/v2/data/query.json"
_MODALITY_MAP = {1: "ISH", 2: "ISH", 3: "IHC"}


class AllenDataset(Base):
    __tablename__ = "allen_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False, unique=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    modality: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    plane_of_section_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    specimen_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)


class AllenBrainConnector(BaseConnector):
    SOURCE_NAME = "allen_brain"
    VERSION = "0.1.0"

    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        response = httpx.get(
            _BASE,
            params={"criteria": "model::SectionDataSet", "num_rows": limit, "start_row": 0},
            timeout=30,
        )
        response.raise_for_status()
        for record in response.json().get("msg", []):
            if not record.get("failed", False):
                yield record

    def get_source_id(self, raw: dict) -> str:
        return str(raw["id"])

    def normalize_dataset(self, raw: dict, index_id: int, run_id: int) -> AllenDataset:
        modality = _MODALITY_MAP.get(raw.get("plane_of_section_id"), "Unknown")
        return AllenDataset(
            index_id=index_id,
            source_id=str(raw["id"]),
            title=raw.get("name", ""),
            modality=modality,
            plane_of_section_id=raw.get("plane_of_section_id"),
            specimen_id=raw.get("specimen_id"),
            description=raw.get("description"),
            metadata_json=json.dumps({"plane_of_section_id": raw.get("plane_of_section_id")}),
            run_id=run_id,
        )

    def fetch_subjects(self, dataset_source_id: str) -> Iterator[dict]:
        return iter([])

    def normalize_subject(self, raw: dict, index_id: int) -> Subject:
        return Subject(index_id=index_id, source_subject_id=str(raw.get("id", "")))
