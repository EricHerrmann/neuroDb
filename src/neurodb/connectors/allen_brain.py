import json
from collections.abc import Iterator

import httpx
from sqlalchemy import ForeignKey, Integer, Sequence, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from neurodb.connectors.base import BaseConnector
from neurodb.schema import Base, Subject

_BASE = "https://api.brain-map.org/api/v2/data/query.json"


class AllenDataset(Base):
    __tablename__ = "allen_datasets"

    id: Mapped[int] = mapped_column(Integer, Sequence("allen_datasets_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(
        ForeignKey("datasets_index.id"), nullable=False, unique=True
    )
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
    REFERENCE_PATTERNS = (
        r"mouse\.brain-map\.org/experiment/show/(?P<id>\d+)",
        r"brain-map\.org/.+SectionDataSet\[id\$eq(?P<id>\d+)\]",
    )

    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        try:
            response = httpx.get(
                _BASE,
                params={"criteria": "model::SectionDataSet", "num_rows": limit, "start_row": 0},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"Allen Brain Atlas request timed out ({_BASE})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Allen Brain Atlas API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        for record in response.json().get("msg", []):
            if not record.get("failed", False):
                yield record

    def get_source_id(self, raw: dict) -> str:
        return str(raw["id"])

    def normalize_dataset(self, raw: dict, index_id: int, run_id: int) -> AllenDataset:
        return AllenDataset(
            index_id=index_id,
            source_id=str(raw["id"]),
            title=raw.get("name") or "",
            modality="ISH",
            plane_of_section_id=raw.get("plane_of_section_id"),
            specimen_id=raw.get("specimen_id"),
            description=raw.get("description"),
            metadata_json=json.dumps(raw),
            run_id=run_id,
        )

    def fetch_by_id(self, dataset_id: str) -> dict:
        try:
            response = httpx.get(
                _BASE,
                params={"criteria": f"model::SectionDataSet[id$eq{dataset_id}]", "num_rows": 1},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"Allen Brain Atlas request timed out ({_BASE})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Allen Brain Atlas API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        records = response.json().get("msg", [])
        if not records:
            raise RuntimeError(f"Allen Brain Atlas dataset {dataset_id} not found")
        return records[0]

    def search_by_keyword(self, query: str, limit: int = 10) -> list[dict]:
        try:
            response = httpx.get(
                _BASE,
                params={
                    "criteria": f"model::SectionDataSet[name$li*{query}*]",
                    "num_rows": limit,
                    "start_row": 0,
                },
                timeout=30,
            )
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"Allen Brain Atlas request timed out ({_BASE})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Allen Brain Atlas API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        return [r for r in response.json().get("msg", []) if not r.get("failed", False)]

    def fetch_subjects(self, dataset_source_id: str) -> Iterator[dict]:
        return iter([])

    def normalize_subject(self, raw: dict, index_id: int) -> Subject:
        return Subject(index_id=index_id, source_subject_id=str(raw.get("id", "")))
