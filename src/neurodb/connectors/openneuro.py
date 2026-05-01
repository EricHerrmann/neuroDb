import json
from typing import Any, Iterator
import httpx
from sqlalchemy import String, Integer, ForeignKey, Sequence, Text
from sqlalchemy.orm import Mapped, mapped_column
from neurodb.schema import Base, Subject
from neurodb.connectors.base import BaseConnector

GRAPHQL_URL = "https://openneuro.org/crn/graphql"

_DATASETS_QUERY = """
query ListDatasets($first: Int) {
  datasets(first: $first, orderBy: { created: descending }) {
    edges {
      node {
        id
        name
        metadata {
          species
          modalities
          associatedPaperDOI
          ages
        }
        draft {
          readme
          description {
            BIDSVersion
          }
        }
      }
    }
  }
}
"""

_DATASET_BY_ID_QUERY = """
query GetDataset($id: ID!) {
  dataset(id: $id) {
    id
    name
    metadata {
      species
      modalities
      associatedPaperDOI
      ages
    }
    draft {
      readme
      description {
        BIDSVersion
      }
    }
  }
}
"""

_SEARCH_QUERY = """
query SearchDatasets($search: String, $first: Int) {
  datasets(search: $search, first: $first, orderBy: { created: descending }) {
    edges {
      node {
        id
        name
        metadata {
          species
          modalities
          associatedPaperDOI
          ages
        }
        draft {
          readme
          description {
            BIDSVersion
          }
        }
      }
    }
  }
}
"""


class OpenNeuroDataset(Base):
    """Source-specific table for OpenNeuro datasets.
    References datasets_index via index_id for cross-cutting queries.
    """
    __tablename__ = "openneuro_datasets"

    id: Mapped[int] = mapped_column(Integer, Sequence("openneuro_datasets_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False, unique=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    modality: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    n_subjects: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bids_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)


class OpenNeuroConnector(BaseConnector):
    SOURCE_NAME = "openneuro"
    VERSION = "0.1.0"

    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        try:
            response = httpx.post(
                GRAPHQL_URL,
                json={"query": _DATASETS_QUERY, "variables": {"first": limit}},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"OpenNeuro request timed out ({GRAPHQL_URL})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"OpenNeuro API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        edges = response.json()["data"]["datasets"]["edges"]
        for edge in edges:
            yield edge["node"]

    def get_source_id(self, raw: dict) -> str:
        return raw["id"]

    def normalize_dataset(self, raw: dict, index_id: int, run_id: int) -> OpenNeuroDataset:
        meta = raw.get("metadata") or {}
        draft = raw.get("draft") or {}
        draft_desc = draft.get("description") or {}
        modalities = meta.get("modalities") or []
        modality = modalities[0] if modalities else None
        ages = meta.get("ages") or []
        return OpenNeuroDataset(
            index_id=index_id,
            source_id=raw["id"],
            title=raw.get("name", ""),
            doi=meta.get("associatedPaperDOI"),
            modality=modality,
            n_subjects=len(ages) if ages else None,
            bids_version=draft_desc.get("BIDSVersion"),
            description=draft.get("readme"),
            metadata_json=json.dumps(meta),
            run_id=run_id,
        )

    def fetch_by_id(self, dataset_id: str) -> dict:
        try:
            response = httpx.post(
                GRAPHQL_URL,
                json={"query": _DATASET_BY_ID_QUERY, "variables": {"id": dataset_id}},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"OpenNeuro request timed out ({GRAPHQL_URL})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"OpenNeuro API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        body = response.json()
        if body.get("errors"):
            msg = body["errors"][0]["message"]
            raise RuntimeError(f"OpenNeuro GraphQL error for {dataset_id}: {msg}")
        return body["data"]["dataset"]

    def search_by_keyword(self, query: str, limit: int = 10) -> list[dict]:
        try:
            response = httpx.post(
                GRAPHQL_URL,
                json={"query": _SEARCH_QUERY, "variables": {"search": query, "first": limit}},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"OpenNeuro request timed out ({GRAPHQL_URL})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"OpenNeuro API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        body = response.json()
        if body.get("errors"):
            msg = body["errors"][0]["message"]
            raise RuntimeError(f"OpenNeuro GraphQL error: {msg}")
        edges = body["data"]["datasets"]["edges"]
        return [edge["node"] for edge in edges]

    def fetch_subjects(self, dataset_source_id: str) -> Iterator[dict]:
        # OpenNeuro participant data requires BIDS sidecar; stubbed for MVP
        return iter([])

    def normalize_subject(self, raw: dict, index_id: int) -> Subject:
        return Subject(
            index_id=index_id,
            source_subject_id=raw.get("participant_id", ""),
            age=raw.get("age"),
            sex=raw.get("sex"),
            diagnosis=raw.get("diagnosis"),
        )
