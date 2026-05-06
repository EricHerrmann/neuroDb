# Phase 6 — NeuroVault + DANDI Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add NeuroVault and DANDI as ingested sources, including a two-stage NWB enrichment pass for DANDI that downloads and parses one NWB file per dandiset.

**Architecture:** Two new connectors (`neurovault.py`, `dandi.py`) follow the existing pattern — each defines its SQLAlchemy model and `BaseConnector` subclass. A new `neurodb/enrichment.py` module handles DANDI NWB download/parse; `scripts/enrich.py` is the thin CLI wrapper. `create_views` in `db.py` is extended with two new UNION branches. All integration tests use SQLite in-memory; unit tests mock httpx.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x, httpx, pynwb, h5py, dandi Python client, pytest, DuckDB (production), SQLite (tests).

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `src/neurodb/connectors/neurovault.py` | NeuroVaultDataset model + NeuroVaultConnector |
| Create | `src/neurodb/connectors/dandi.py` | DandiDataset model + DandiConnector |
| Create | `src/neurodb/enrichment.py` | `_download_first_nwb`, `_parse_nwb`, `run_enrichment` |
| Create | `scripts/enrich.py` | CLI wrapper for `run_enrichment` |
| Create | `tests/fixtures/neurovault_sample.json` | 2-collection fixture for NeuroVault unit/integration tests |
| Create | `tests/fixtures/dandi_api_sample.json` | 2-dandiset fixture for DANDI unit/integration tests |
| Create | `tests/fixtures/make_dandi_fixture.py` | One-time script to generate `dandi_sample.nwb` |
| Create | `tests/fixtures/dandi_sample.nwb` | Minimal real NWB file (1 electrode, 1 group) — generated then committed |
| Create | `tests/unit/test_neurovault_connector.py` | Unit tests for NeuroVault connector |
| Create | `tests/unit/test_dandi_connector.py` | Unit tests for DANDI connector |
| Create | `tests/integration/test_neurovault_ingest.py` | Full ingest + idempotency test for NeuroVault |
| Create | `tests/integration/test_dandi_ingest.py` | Full ingest + idempotency test for DANDI |
| Create | `tests/integration/test_dandi_enrich.py` | Enrichment + idempotency + error-handling tests |
| Create | `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6.md` | Manual test plan for Phase 6 |
| Modify | `pyproject.toml` | Add dandi, pynwb, h5py dependencies |
| Modify | `src/neurodb/db.py` | Extend `create_views` with neurovault + dandi UNION branches |
| Modify | `scripts/ingest.py` | Register `neurovault` and `dandi` sources in CONNECTORS dict |
| Modify | `tests/integration/test_unified_view.py` | Seed + assert all 4 sources in view tests |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dandi, pynwb, h5py to pyproject.toml**

Replace the `dependencies` block:

```toml
dependencies = [
    "dandi>=0.62",
    "duckdb>=1.2",
    "duckdb-engine>=0.14",
    "h5py>=3.10",
    "httpx>=0.28.1",
    "pandas>=3.0.2",
    "pynwb>=2.8",
    "sqlalchemy>=2.0.49",
    "streamlit>=1.56.0",
]
```

- [ ] **Step 2: Sync dependencies**

```bash
uv sync
```

Expected: resolves and installs dandi, pynwb, h5py without error.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add dandi, pynwb, h5py dependencies for Phase 6"
```

---

## Task 2: NeuroVault Connector (TDD)

**Files:**
- Create: `tests/fixtures/neurovault_sample.json`
- Create: `tests/unit/test_neurovault_connector.py`
- Create: `src/neurodb/connectors/neurovault.py`

- [ ] **Step 1: Create the fixture file**

Write `tests/fixtures/neurovault_sample.json`:

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Working Memory fMRI Study",
      "doi": "10.1016/j.neuroimage.2021.01.001",
      "number_of_images": 42,
      "number_of_subjects": 30,
      "cognitive_paradigm_cog_atlas": "working memory",
      "repetition_time": 2.0,
      "resolution": "2mm",
      "description": "fMRI study of working memory in healthy adults"
    },
    {
      "id": 2,
      "name": "Pain Perception fMRI",
      "doi": null,
      "number_of_images": 18,
      "number_of_subjects": null,
      "cognitive_paradigm_cog_atlas": null,
      "repetition_time": 1.5,
      "resolution": null,
      "description": null
    }
  ]
}
```

- [ ] **Step 2: Write failing unit tests**

Write `tests/unit/test_neurovault_connector.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import httpx
from neurodb.connectors.neurovault import NeuroVaultConnector, NeuroVaultDataset

FIXTURE = Path(__file__).parent.parent / "fixtures" / "neurovault_sample.json"


def _mock_get(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_fetch_datasets_returns_two():
    conn = NeuroVaultConnector()
    with patch("neurodb.connectors.neurovault.httpx.get", side_effect=_mock_get):
        results = list(conn.fetch_datasets(limit=10))
    assert len(results) == 2


def test_get_source_id():
    conn = NeuroVaultConnector()
    assert conn.get_source_id({"id": 1}) == "1"


def test_normalize_dataset_maps_all_fields():
    conn = NeuroVaultConnector()
    data = json.loads(FIXTURE.read_text())
    raw = data["results"][0]
    ds = conn.normalize_dataset(raw, index_id=1, run_id=1)
    assert isinstance(ds, NeuroVaultDataset)
    assert ds.source_id == "1"
    assert ds.title == "Working Memory fMRI Study"
    assert ds.doi == "10.1016/j.neuroimage.2021.01.001"
    assert ds.n_images == 42
    assert ds.n_subjects == 30
    assert ds.cognitive_paradigm == "working memory"
    assert ds.tr == 2.0
    assert ds.resolution == "2mm"
    assert ds.index_id == 1
    assert json.loads(ds.metadata_json)["id"] == 1


def test_normalize_dataset_handles_null_fields():
    conn = NeuroVaultConnector()
    data = json.loads(FIXTURE.read_text())
    raw = data["results"][1]
    ds = conn.normalize_dataset(raw, index_id=2, run_id=1)
    assert ds.doi is None
    assert ds.n_subjects is None
    assert ds.cognitive_paradigm is None
    assert ds.resolution is None


def test_fetch_datasets_raises_on_timeout():
    conn = NeuroVaultConnector()
    with patch(
        "neurodb.connectors.neurovault.httpx.get",
        side_effect=httpx.TimeoutException("timed out"),
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            list(conn.fetch_datasets())


def test_fetch_datasets_raises_on_http_error():
    conn = NeuroVaultConnector()
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = "Service Unavailable"
    with patch(
        "neurodb.connectors.neurovault.httpx.get",
        side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=mock_response),
    ):
        with pytest.raises(RuntimeError, match="503"):
            list(conn.fetch_datasets())
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
uv run pytest tests/unit/test_neurovault_connector.py -v
```

Expected: `ModuleNotFoundError: No module named 'neurodb.connectors.neurovault'`

- [ ] **Step 4: Implement the connector**

Write `src/neurodb/connectors/neurovault.py`:

```python
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

    def fetch_subjects(self, dataset_source_id: str) -> Iterator[dict]:
        return iter([])

    def normalize_subject(self, raw: dict, index_id: int) -> Subject:
        return Subject(index_id=index_id, source_subject_id=str(raw.get("id", "")))
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/unit/test_neurovault_connector.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/neurovault_sample.json tests/unit/test_neurovault_connector.py src/neurodb/connectors/neurovault.py
git commit -m "feat: NeuroVault connector and model"
```

---

## Task 3: NeuroVault Integration, Views, and ingest.py

**Files:**
- Create: `tests/integration/test_neurovault_ingest.py`
- Modify: `src/neurodb/db.py` (add neurovault UNION branch to `create_views`)
- Modify: `scripts/ingest.py` (register `neurovault` source)
- Modify: `tests/integration/test_unified_view.py` (seed + assert neurovault)

- [ ] **Step 1: Write the failing integration test**

Write `tests/integration/test_neurovault_ingest.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.provenance import run_ingest
from neurodb.connectors.neurovault import NeuroVaultConnector, NeuroVaultDataset
from neurodb.schema import DatasetIndex, IngestRun

FIXTURE = Path("tests/fixtures/neurovault_sample.json")


def _mock_get(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_full_ingest_stores_datasets():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.neurovault.httpx.get", side_effect=_mock_get):
        run_ingest(engine, connector=NeuroVaultConnector(), limit=10)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 2
        assert session.query(NeuroVaultDataset).count() == 2
        assert session.query(IngestRun).count() == 1
        ds = session.query(NeuroVaultDataset).filter_by(source_id="1").one()
        assert ds.title == "Working Memory fMRI Study"
        assert ds.doi == "10.1016/j.neuroimage.2021.01.001"
        assert ds.n_images == 42
        assert ds.n_subjects == 30
        assert ds.cognitive_paradigm == "working memory"
        assert ds.tr == 2.0
        idx = session.query(DatasetIndex).filter_by(source_id="1").one()
        assert idx.source == "neurovault"


def test_double_ingest_does_not_duplicate():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.neurovault.httpx.get", side_effect=_mock_get):
        run_ingest(engine, connector=NeuroVaultConnector(), limit=10)
        run_ingest(engine, connector=NeuroVaultConnector(), limit=10)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 2
        assert session.query(NeuroVaultDataset).count() == 2
```

- [ ] **Step 2: Run test — verify it fails**

```bash
uv run pytest tests/integration/test_neurovault_ingest.py -v
```

Expected: FAIL — `neurovault_datasets` table not found or assertion errors.

- [ ] **Step 3: Update create_views in db.py**

In `src/neurodb/db.py`, replace the `conn.execute(text("""CREATE VIEW v_all_datasets AS ...`  block (lines 34–63) with:

```python
        conn.execute(text("""
            CREATE VIEW v_all_datasets AS
            SELECT
                di.id        AS index_id,
                di.source,
                di.source_id,
                od.title,
                od.doi,
                od.modality,
                od.n_subjects,
                od.description,
                di.run_id
            FROM datasets_index di
            JOIN openneuro_datasets od ON od.index_id = di.id
            WHERE di.source = 'openneuro'
            UNION ALL
            SELECT
                di.id        AS index_id,
                di.source,
                di.source_id,
                ad.title,
                NULL         AS doi,
                ad.modality,
                NULL         AS n_subjects,
                ad.description,
                di.run_id
            FROM datasets_index di
            JOIN allen_datasets ad ON ad.index_id = di.id
            WHERE di.source = 'allen_brain'
            UNION ALL
            SELECT
                di.id        AS index_id,
                di.source,
                di.source_id,
                nv.title,
                nv.doi,
                'fMRI'       AS modality,
                nv.n_subjects,
                nv.description,
                di.run_id
            FROM datasets_index di
            JOIN neurovault_datasets nv ON nv.index_id = di.id
            WHERE di.source = 'neurovault'
        """))
```

- [ ] **Step 4: Update ingest.py**

In `scripts/ingest.py`, add the import and register the connector:

```python
from neurodb.connectors.openneuro import OpenNeuroConnector
from neurodb.connectors.allen_brain import AllenBrainConnector
from neurodb.connectors.neurovault import NeuroVaultConnector  # noqa: F401 — registers model

CONNECTORS = {
    "openneuro": OpenNeuroConnector,
    "allen_brain": AllenBrainConnector,
    "neurovault": NeuroVaultConnector,
}
```

- [ ] **Step 5: Update test_unified_view.py**

In `tests/integration/test_unified_view.py`, add the import at the top:

```python
from neurodb.connectors.neurovault import NeuroVaultDataset
```

Add to the `_seed` function (after the existing `session.add(AllenDataset(...))` line):

```python
        idx3 = DatasetIndex(source="neurovault", source_id="1", run_id=run.id)
        session.add(idx3)
        session.flush()
        session.add(NeuroVaultDataset(index_id=idx3.id, source_id="1",
                                      title="Working Memory fMRI", n_subjects=30,
                                      run_id=run.id))
```

Add a new test at the end of the file:

```python
def test_unified_view_contains_neurovault():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source")).fetchall()
    sources = {r[0]: r[1] for r in rows}
    assert sources["neurovault"] == 1
```

- [ ] **Step 6: Run all tests — verify they pass**

```bash
uv run pytest tests/ -v
```

Expected: all previously passing tests still pass + new tests pass.

- [ ] **Step 7: Commit**

```bash
git add tests/integration/test_neurovault_ingest.py src/neurodb/db.py scripts/ingest.py tests/integration/test_unified_view.py
git commit -m "feat: wire NeuroVault into ingest, views, and integration tests"
```

---

## Task 4: DANDI API Connector (TDD)

**Files:**
- Create: `tests/fixtures/dandi_api_sample.json`
- Create: `tests/unit/test_dandi_connector.py`
- Create: `src/neurodb/connectors/dandi.py`

- [ ] **Step 1: Create the fixture file**

Write `tests/fixtures/dandi_api_sample.json`:

```json
{
  "count": 2,
  "next": null,
  "results": [
    {
      "identifier": "000003",
      "created": "2020-03-15T00:00:00Z",
      "modified": "2021-08-13T00:00:00Z",
      "contact_person": "Researcher Name",
      "embargo_status": "OPEN",
      "most_recent_published_version": {
        "version": "0.210813.2352",
        "name": "Electrophysiology in hippocampus during spatial navigation",
        "asset_summary": {
          "numberOfSubjects": 5,
          "numberOfFiles": 25,
          "dataStandard": [{"name": "NWB: Neurodata Without Borders"}],
          "species": [{"name": "Mus musculus - House mouse"}]
        }
      },
      "draft_version": null
    },
    {
      "identifier": "000004",
      "created": "2020-04-01T00:00:00Z",
      "modified": "2021-09-01T00:00:00Z",
      "contact_person": "Another Researcher",
      "embargo_status": "OPEN",
      "most_recent_published_version": null,
      "draft_version": {
        "version": "draft",
        "name": "Calcium imaging in visual cortex",
        "asset_summary": {
          "numberOfSubjects": 3,
          "numberOfFiles": 10,
          "dataStandard": [{"name": "NWB: Neurodata Without Borders"}],
          "species": [{"name": "Mus musculus - House mouse"}]
        }
      }
    }
  ]
}
```

- [ ] **Step 2: Write failing unit tests**

Write `tests/unit/test_dandi_connector.py`:

```python
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
    raw = data["results"][1]  # has draft_version, not most_recent_published_version
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
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
uv run pytest tests/unit/test_dandi_connector.py -v
```

Expected: `ModuleNotFoundError: No module named 'neurodb.connectors.dandi'`

- [ ] **Step 4: Implement the DANDI connector**

Write `src/neurodb/connectors/dandi.py`:

```python
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
            params = None  # subsequent pages: the next URL includes pagination params

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
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/unit/test_dandi_connector.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/dandi_api_sample.json tests/unit/test_dandi_connector.py src/neurodb/connectors/dandi.py
git commit -m "feat: DANDI connector and model"
```

---

## Task 5: DANDI Integration, Views, and ingest.py

**Files:**
- Create: `tests/integration/test_dandi_ingest.py`
- Modify: `src/neurodb/db.py` (add dandi UNION branch)
- Modify: `scripts/ingest.py` (register `dandi`)
- Modify: `tests/integration/test_unified_view.py` (seed + assert dandi)

- [ ] **Step 1: Write failing integration test**

Write `tests/integration/test_dandi_ingest.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.provenance import run_ingest
from neurodb.connectors.dandi import DandiConnector, DandiDataset
from neurodb.schema import DatasetIndex, IngestRun

FIXTURE = Path("tests/fixtures/dandi_api_sample.json")


def _mock_get(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_full_ingest_stores_datasets():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.dandi.httpx.get", side_effect=_mock_get):
        run_ingest(engine, connector=DandiConnector(), limit=10)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 2
        assert session.query(DandiDataset).count() == 2
        assert session.query(IngestRun).count() == 1
        ds = session.query(DandiDataset).filter_by(source_id="000003").one()
        assert ds.title == "Electrophysiology in hippocampus during spatial navigation"
        assert ds.species == "Mus musculus - House mouse"
        assert ds.n_subjects == 5
        assert ds.enriched_at is None
        assert ds.brain_regions is None
        idx = session.query(DatasetIndex).filter_by(source_id="000003").one()
        assert idx.source == "dandi"


def test_double_ingest_does_not_duplicate():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.dandi.httpx.get", side_effect=_mock_get):
        run_ingest(engine, connector=DandiConnector(), limit=10)
        run_ingest(engine, connector=DandiConnector(), limit=10)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 2
        assert session.query(DandiDataset).count() == 2
```

- [ ] **Step 2: Run test — verify it fails**

```bash
uv run pytest tests/integration/test_dandi_ingest.py -v
```

Expected: FAIL — `dandi_datasets` table not found.

- [ ] **Step 3: Add dandi UNION branch to create_views**

In `src/neurodb/db.py`, append to the `v_all_datasets` CREATE VIEW statement (after the neurovault UNION ALL block, before the closing `"""`):

```sql
            UNION ALL
            SELECT
                di.id        AS index_id,
                di.source,
                di.source_id,
                dd.title,
                dd.doi,
                dd.modality,
                dd.n_subjects,
                dd.cognitive_paradigm AS description,
                di.run_id
            FROM datasets_index di
            JOIN dandi_datasets dd ON dd.index_id = di.id
            WHERE di.source = 'dandi'
```

- [ ] **Step 4: Update ingest.py**

In `scripts/ingest.py`, add the DANDI import and connector:

```python
from neurodb.connectors.openneuro import OpenNeuroConnector
from neurodb.connectors.allen_brain import AllenBrainConnector
from neurodb.connectors.neurovault import NeuroVaultConnector  # noqa: F401 — registers model
from neurodb.connectors.dandi import DandiConnector  # noqa: F401 — registers model

CONNECTORS = {
    "openneuro": OpenNeuroConnector,
    "allen_brain": AllenBrainConnector,
    "neurovault": NeuroVaultConnector,
    "dandi": DandiConnector,
}
```

- [ ] **Step 5: Update test_unified_view.py**

Add the import at the top of `tests/integration/test_unified_view.py`:

```python
from neurodb.connectors.dandi import DandiDataset
```

Add to the `_seed` function (after the NeuroVaultDataset line added in Task 3):

```python
        idx4 = DatasetIndex(source="dandi", source_id="000003", run_id=run.id)
        session.add(idx4)
        session.flush()
        session.add(DandiDataset(index_id=idx4.id, source_id="000003",
                                  title="Ephys in hippocampus", modality="NWB",
                                  n_subjects=5, run_id=run.id))
```

Add a new test at the end of the file:

```python
def test_unified_view_contains_dandi():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source")).fetchall()
    sources = {r[0]: r[1] for r in rows}
    assert sources["dandi"] == 1
```

- [ ] **Step 6: Run all tests — verify they pass**

```bash
uv run pytest tests/ -v
```

Expected: all previously passing tests still pass + new DANDI tests pass.

- [ ] **Step 7: Commit**

```bash
git add tests/integration/test_dandi_ingest.py src/neurodb/db.py scripts/ingest.py tests/integration/test_unified_view.py
git commit -m "feat: wire DANDI into ingest, views, and integration tests"
```

---

## Task 6: Generate NWB Fixture

**Files:**
- Create: `tests/fixtures/make_dandi_fixture.py`
- Create: `tests/fixtures/dandi_sample.nwb` (generated then committed)

- [ ] **Step 1: Write the fixture generator script**

Write `tests/fixtures/make_dandi_fixture.py`:

```python
#!/usr/bin/env python
"""Generate a minimal NWB fixture for DANDI enrichment tests.

Run once: uv run tests/fixtures/make_dandi_fixture.py
Output:   tests/fixtures/dandi_sample.nwb

The file is committed to git so tests never need to regenerate it.
"""
from datetime import datetime, timezone
from pathlib import Path
from pynwb import NWBFile, NWBHDF5IO

OUTPUT = Path(__file__).parent / "dandi_sample.nwb"


def main():
    nwbfile = NWBFile(
        session_description="Motor cortex recording during lever pressing task",
        identifier="test-fixture-001",
        session_start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    device = nwbfile.create_device(name="array", description="test array", manufacturer="test")
    nwbfile.create_electrode_group(
        name="tetrode1",
        description="test electrode group",
        location="CA1",
        device=device,
    )
    nwbfile.add_electrode_column(name="sampling_rate", description="sampling rate in Hz")
    nwbfile.add_electrode(
        x=1.0,
        y=2.0,
        z=3.0,
        imp=-1.0,
        location="CA1",
        filtering="300-3000 Hz",
        group=nwbfile.electrode_groups["tetrode1"],
        group_name="tetrode1",
        sampling_rate=30000.0,
    )
    with NWBHDF5IO(str(OUTPUT), "w") as io:
        io.write(nwbfile)
    print(f"Written: {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the fixture**

```bash
uv run tests/fixtures/make_dandi_fixture.py
```

Expected output: `Written: tests/fixtures/dandi_sample.nwb (NNNN bytes)`

Verify the file exists:

```bash
ls -lh tests/fixtures/dandi_sample.nwb
```

Expected: file present, size in KB range (not MB).

- [ ] **Step 3: Commit fixture and generator**

```bash
git add tests/fixtures/make_dandi_fixture.py tests/fixtures/dandi_sample.nwb
git commit -m "test: add minimal NWB fixture for DANDI enrichment tests"
```

---

## Task 7: DANDI Enrichment Module (TDD)

**Files:**
- Create: `tests/integration/test_dandi_enrich.py`
- Create: `src/neurodb/enrichment.py`

- [ ] **Step 1: Write the failing enrichment tests**

Write `tests/integration/test_dandi_enrich.py`:

```python
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

    # Return a path that doesn't exist — _parse_nwb will raise
    with patch("neurodb.enrichment._download_first_nwb", return_value="/nonexistent/path.nwb"):
        count = run_enrichment(engine)

    assert count == 0
    with get_session(engine) as session:
        rec = session.query(DandiDataset).filter_by(source_id="000003").one()
        assert rec.enriched_at is not None
        assert rec.enriched_at.startswith("ERROR")
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run pytest tests/integration/test_dandi_enrich.py -v
```

Expected: `ModuleNotFoundError: No module named 'neurodb.enrichment'`

- [ ] **Step 3: Implement enrichment.py**

Write `src/neurodb/enrichment.py`:

```python
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import Engine
from neurodb.db import get_session


def _download_first_nwb(source_id: str) -> str | None:
    """Download the first NWB asset for a dandiset to a temp file. Returns path or None."""
    from dandi.dandiapi import DandiAPIClient
    with DandiAPIClient() as client:
        dandiset = client.get_dandiset(source_id)
        for asset in dandiset.get_assets():
            if asset.path.endswith(".nwb"):
                tmp = tempfile.NamedTemporaryFile(suffix=".nwb", delete=False)
                tmp.close()
                asset.download(tmp.name)
                return tmp.name
    return None


def _parse_nwb(path: str) -> dict:
    """Extract enrichment fields from an NWB file. Raises on parse failure."""
    import h5py
    from pynwb import NWBHDF5IO

    nwb_version = None
    with h5py.File(path, "r") as hf:
        raw_ver = hf.attrs.get("nwb_version")
        if raw_ver is not None:
            nwb_version = raw_ver.decode() if isinstance(raw_ver, bytes) else str(raw_ver)

    electrode_count = None
    sampling_rate = None
    brain_regions = None
    cognitive_paradigm = None

    with NWBHDF5IO(path, "r", load_namespaces=True) as io:
        nwb = io.read()

        if nwb.electrodes is not None:
            electrode_count = len(nwb.electrodes)
            df = nwb.electrodes.to_dataframe()
            if "sampling_rate" in df.columns:
                rates = df["sampling_rate"].dropna()
                if not rates.empty:
                    sampling_rate = float(rates.iloc[0])

        if nwb.electrode_groups:
            locations = [eg.location for eg in nwb.electrode_groups.values() if eg.location]
            if locations:
                brain_regions = json.dumps(list(dict.fromkeys(locations)))

        if nwb.session_description:
            cognitive_paradigm = nwb.session_description[:256]

    return {
        "electrode_count": electrode_count,
        "sampling_rate": sampling_rate,
        "brain_regions": brain_regions,
        "cognitive_paradigm": cognitive_paradigm,
        "nwb_version": nwb_version,
    }


def run_enrichment(engine: Engine, limit: int | None = None) -> int:
    """Enrich unenriched DANDI records with NWB metadata. Returns count enriched."""
    from neurodb.connectors.dandi import DandiDataset

    with get_session(engine) as session:
        query = session.query(DandiDataset).filter(DandiDataset.enriched_at.is_(None))
        if limit is not None:
            query = query.limit(limit)
        records = list(query)

    enriched_count = 0
    for record in records:
        tmp_path = None
        try:
            tmp_path = _download_first_nwb(record.source_id)
            if tmp_path is None:
                print(f"  {record.source_id}: no NWB asset found, skipping")
                continue
            fields = _parse_nwb(tmp_path)
            with get_session(engine) as session:
                rec = session.get(DandiDataset, record.id)
                for k, v in fields.items():
                    setattr(rec, k, v)
                rec.enriched_at = datetime.now(timezone.utc).isoformat()
            enriched_count += 1
            print(f"  {record.source_id}: enriched ({fields['electrode_count']} electrodes)")
        except Exception as e:
            print(f"  WARNING: {record.source_id}: enrichment failed: {e}")
            try:
                with get_session(engine) as session:
                    rec = session.get(DandiDataset, record.id)
                    if rec is not None:
                        rec.enriched_at = f"ERROR:{str(e)[:200]}"
            except Exception:
                pass
        finally:
            if tmp_path is not None:
                p = Path(tmp_path)
                if p.exists():
                    p.unlink()

    return enriched_count
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/integration/test_dandi_enrich.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass (previously 35 + new tests).

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_dandi_enrich.py src/neurodb/enrichment.py
git commit -m "feat: DANDI NWB enrichment module and integration tests"
```

---

## Task 8: enrich.py CLI Script

**Files:**
- Create: `scripts/enrich.py`

- [ ] **Step 1: Write enrich.py**

Write `scripts/enrich.py`:

```python
#!/usr/bin/env python
"""CLI: enrich source records with file-level metadata.

Usage:
    uv run scripts/enrich.py --source dandi --limit 10 --db neurodb.duckdb
"""
import argparse
from neurodb.db import get_engine, init_db, create_views
from neurodb.connectors.dandi import DandiDataset  # noqa: F401 — registers model
from neurodb.enrichment import run_enrichment

SOURCES = ["dandi"]


def main():
    parser = argparse.ArgumentParser(description="Enrich neuro records with file-level metadata")
    parser.add_argument("--source", choices=SOURCES, required=True)
    parser.add_argument("--limit", type=int, default=None, help="Max records to enrich (default: all)")
    parser.add_argument("--db", default="neurodb.duckdb")
    args = parser.parse_args()

    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    create_views(engine)
    count = run_enrichment(engine, limit=args.limit)
    print(f"Enrichment complete: {count} records enriched.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script runs (help only — no network calls)**

```bash
uv run scripts/enrich.py --help
```

Expected: prints usage including `--source`, `--limit`, `--db`.

- [ ] **Step 3: Commit**

```bash
git add scripts/enrich.py
git commit -m "feat: enrich.py CLI for DANDI NWB enrichment"
```

---

## Task 9: Manual Test Plan

**Files:**
- Create: `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6.md`

- [ ] **Step 1: Write the manual test plan**

Write `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6.md`:

```markdown
# Phase 6 Manual Test Plan — NeuroVault + DANDI Connectors

**Status:** Pending
**Tester:** Eric Herrmann
**Scope:** NeuroVault ingest, DANDI ingest, DANDI NWB enrichment, unified view with 4 sources
**Date:** <!-- fill in on execution -->

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

```bash
git status          # confirm on master, clean working tree
uv sync             # ensure deps installed
uv run pytest tests/ -v   # all tests pass before manual testing begins
```

Expected: all automated tests pass.

---

## Test 1 — NeuroVault ingest

```bash
uv run scripts/ingest.py --source neurovault --limit 50
```

| # | Step | Expected |
|---|------|----------|
| 1.1 | Command exits without error | `Ingest complete: run_id=N, source=neurovault, at=<timestamp>` |
| 1.2 | Records visible in unified view | See query below |

```bash
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source"
```

| # | Step | Expected |
|---|------|----------|
| 1.3 | `neurovault` row appears | Count > 0 |

---

## Test 2 — DANDI ingest (stage 1)

```bash
uv run scripts/ingest.py --source dandi --limit 50
```

| # | Step | Expected |
|---|------|----------|
| 2.1 | Command exits without error | `Ingest complete: run_id=N, source=dandi, at=<timestamp>` |
| 2.2 | DANDI records visible | `dandi` row in GROUP BY query above with count > 0 |
| 2.3 | NWB fields are null pre-enrichment | See query below |

```bash
uv run scripts/query_cli.py --sql "SELECT source_id, electrode_count, brain_regions FROM dandi_datasets LIMIT 5"
```

| # | Step | Expected |
|---|------|----------|
| 2.4 | `electrode_count` and `brain_regions` are NULL | NWB fields not yet populated |

---

## Test 3 — DANDI NWB enrichment (stage 2)

```bash
uv run scripts/enrich.py --source dandi --limit 5
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | Command exits without error | `Enrichment complete: N records enriched.` |
| 3.2 | Per-record progress printed | Lines like `  000003: enriched (N electrodes)` |

```bash
uv run scripts/query_cli.py --sql "SELECT source_id, electrode_count, brain_regions, enriched_at FROM dandi_datasets WHERE enriched_at IS NOT NULL LIMIT 5"
```

| # | Step | Expected |
|---|------|----------|
| 3.3 | `enriched_at` is set (not NULL, not ERROR) | ISO timestamp visible |
| 3.4 | `electrode_count` populated | Integer > 0 or 0 (valid) |
| 3.5 | `brain_regions` populated | JSON array string or NULL |

---

## Test 4 — Unified view with 4 sources

```bash
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source ORDER BY source"
```

| # | Step | Expected |
|---|------|----------|
| 4.1 | 4 rows returned | `allen_brain`, `dandi`, `neurovault`, `openneuro` all present |
| 4.2 | All counts > 0 | Each source ingested at least some records |

---

## Test 5 — Idempotent re-ingest

```bash
uv run scripts/ingest.py --source neurovault --limit 50
uv run scripts/ingest.py --source dandi --limit 50
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source"
```

| # | Step | Expected |
|---|------|----------|
| 5.1 | Both re-ingests exit without error | Exit code 0 |
| 5.2 | Row counts unchanged | Same counts as Test 4 |

---

## Test 6 — Idempotent re-enrichment

```bash
uv run scripts/enrich.py --source dandi --limit 5
```

| # | Step | Expected |
|---|------|----------|
| 6.1 | Command exits without error | `Enrichment complete: 0 records enriched.` (already enriched records skipped) |

---

## Pass Criteria

- [ ] NeuroVault ingest completes without error
- [ ] DANDI ingest completes without error; NWB fields are NULL before enrichment
- [ ] Enrichment populates NWB fields on DANDI records; `enriched_at` is a timestamp (not ERROR)
- [ ] All 4 sources appear in `v_all_datasets` with count > 0
- [ ] Re-ingest of both sources is idempotent (no duplicate rows)
- [ ] Re-enrichment is idempotent (0 records enriched on second pass)

**Sign-off:** _________________________________ Date: _____________
```

- [ ] **Step 2: Commit**

```bash
git add docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6.md
git commit -m "docs: Phase 6 manual test plan"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] NeuroVault connector + schema → Tasks 2, 3
- [x] DANDI connector + schema → Tasks 4, 5
- [x] `enrich.py` CLI → Task 8
- [x] `neurodb/enrichment.py` with `_download_first_nwb`, `_parse_nwb`, `run_enrichment` → Task 7
- [x] `v_all_datasets` extended to 4 sources → Tasks 3, 5
- [x] NWB fixture + generator → Task 6
- [x] Unit tests for both connectors → Tasks 2, 4
- [x] Integration tests for both connectors → Tasks 3, 5
- [x] Enrichment integration tests (pass, skip, limit, error) → Task 7
- [x] `ingest.py` wired for both new sources → Tasks 3, 5
- [x] Manual test plan → Task 9
- [x] Dependencies → Task 1

**Type consistency:** `NeuroVaultDataset`, `DandiDataset`, `DandiConnector`, `NeuroVaultConnector`, `run_enrichment`, `_download_first_nwb`, `_parse_nwb` are consistent across all tasks.

**`enriched_at` note:** Spec says `String(32)` but error messages can be up to ~206 chars. Implementation uses `Text` to safely accommodate both ISO timestamps and `"ERROR:<message>"` strings.
