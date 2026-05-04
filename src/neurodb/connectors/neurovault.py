import json
from typing import Iterator
import httpx
from sqlalchemy import Float, ForeignKey, Integer, Sequence, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from neurodb.schema import Base, Subject
from neurodb.connectors.base import BaseConnector

_BASE = "https://neurovault.org/api/collections/"


class NeuroVaultDataset(Base):
    __tablename__ = "neurovault_datasets"

    id: Mapped[int] = mapped_column(Integer, Sequence("neurovault_datasets_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False, unique=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    n_images: Mapped[int | None] = mapped_column(Integer, nullable=True)
    n_subjects: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cognitive_paradigm: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tr: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)


class NeuroVaultConnector(BaseConnector):
    SOURCE_NAME = "neurovault"
    VERSION = "0.1.0"

    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        url: str | None = _BASE
        collected = 0
        while url and collected < limit:
            try:
                response = httpx.get(url, timeout=30)
                response.raise_for_status()
            except httpx.TimeoutException as e:
                raise RuntimeError(f"NeuroVault request timed out ({url})") from e
            except httpx.HTTPStatusError as e:
                raise RuntimeError(
                    f"NeuroVault API returned {e.response.status_code}: {e.response.text[:200]}"
                ) from e
            data = response.json()
            for item in data.get("results", []):
                if collected >= limit:
                    break
                yield item
                collected += 1
            url = data.get("next")

    def get_source_id(self, raw: dict) -> str:
        return str(raw["id"])

    def normalize_dataset(self, raw: dict, index_id: int, run_id: int) -> NeuroVaultDataset:
        return NeuroVaultDataset(
            index_id=index_id,
            source_id=str(raw["id"]),
            title=raw.get("name") or "",
            doi=raw.get("doi") or None,
            n_images=raw.get("number_of_images"),
            n_subjects=raw.get("number_of_subjects"),
            cognitive_paradigm=raw.get("cognitive_paradigm_cog_atlas") or None,
            tr=raw.get("repetition_time"),
            resolution=raw.get("resolution") or None,
            description=raw.get("description") or None,
            metadata_json=json.dumps(raw),
            run_id=run_id,
        )

    def fetch_by_id(self, dataset_id: str) -> dict:
        url = f"{_BASE}{dataset_id}/"
        try:
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"NeuroVault request timed out ({url})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"NeuroVault API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        return response.json()

    def search_by_keyword(self, query: str, limit: int = 10) -> list[dict]:
        try:
            response = httpx.get(_BASE, params={"search": query}, timeout=30)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"NeuroVault request timed out ({_BASE})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"NeuroVault API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        results = response.json().get("results", [])
        return results[:limit]

    def fetch_subjects(self, dataset_source_id: str) -> Iterator[dict]:
        return iter([])

    def normalize_subject(self, raw: dict, index_id: int) -> Subject:
        return Subject(index_id=index_id, source_subject_id=str(raw.get("id", "")))
