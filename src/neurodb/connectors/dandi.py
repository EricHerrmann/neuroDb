import json
from typing import Iterator
import httpx
from sqlalchemy import Float, ForeignKey, Integer, Sequence, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from neurodb.schema import Base, Subject
from neurodb.connectors.base import BaseConnector

_BASE = "https://api.dandiarchive.org/api/dandisets/"


class DandiDataset(Base):
    __tablename__ = "dandi_datasets"

    id: Mapped[int] = mapped_column(Integer, Sequence("dandi_datasets_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False, unique=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    species: Mapped[str | None] = mapped_column(String(128), nullable=True)
    modality: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    n_subjects: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cognitive_paradigm: Mapped[str | None] = mapped_column(String(256), nullable=True)
    brain_regions: Mapped[str | None] = mapped_column(Text, nullable=True)
    sampling_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    electrode_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nwb_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    enriched_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)


class DandiConnector(BaseConnector):
    SOURCE_NAME = "dandi"
    VERSION = "0.1.0"

    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        url: str | None = _BASE
        params: dict | None = {"page_size": min(50, limit)}
        collected = 0
        while url and collected < limit:
            try:
                response = httpx.get(url, params=params, timeout=30)
                response.raise_for_status()
            except httpx.TimeoutException as e:
                raise RuntimeError(f"DANDI request timed out ({url})") from e
            except httpx.HTTPStatusError as e:
                raise RuntimeError(
                    f"DANDI API returned {e.response.status_code}: {e.response.text[:200]}"
                ) from e
            data = response.json()
            for item in data.get("results", []):
                if collected >= limit:
                    break
                yield item
                collected += 1
            url = data.get("next")
            params = None  # subsequent pages: next URL already includes pagination params

    def get_source_id(self, raw: dict) -> str:
        return raw["identifier"]

    def normalize_dataset(self, raw: dict, index_id: int, run_id: int) -> DandiDataset:
        version = raw.get("most_recent_published_version") or raw.get("draft_version") or {}
        asset_summary = version.get("asset_summary") or {}
        species_list = asset_summary.get("species") or []
        data_standard = asset_summary.get("dataStandard") or []
        return DandiDataset(
            index_id=index_id,
            source_id=raw["identifier"],
            title=version.get("name") or "",
            doi=None,
            species=species_list[0]["name"] if species_list else None,
            modality=data_standard[0]["name"] if data_standard else None,
            n_subjects=asset_summary.get("numberOfSubjects"),
            cognitive_paradigm=None,
            brain_regions=None,
            sampling_rate=None,
            electrode_count=None,
            nwb_version=None,
            enriched_at=None,
            metadata_json=json.dumps(raw),
            run_id=run_id,
        )

    def fetch_subjects(self, dataset_source_id: str) -> Iterator[dict]:
        return iter([])

    def normalize_subject(self, raw: dict, index_id: int) -> Subject:
        return Subject(index_id=index_id, source_subject_id=str(raw.get("id", "")))
