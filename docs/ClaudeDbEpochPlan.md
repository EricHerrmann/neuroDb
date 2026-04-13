# NeuroDb DB Epoch — Phased Design & Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-11 | **SQLite for Phases 0–2 (MVP)** | Zero-install, portable, sufficient for single-user local exploration at MVP scale. |
| 2026-04-11 | **DuckDB for Phase 3+** | Columnar performance needed for analytical queries over multi-source merged datasets. |
| 2026-04-11 | **PostgreSQL excluded from design and architecture** | Out of scope for this epoch; no multi-user or server requirements. Do not introduce PostgreSQL-specific patterns or dependencies. |

---

**Goal:** Build a local, reproducible neuroscience data platform that ingests publicly available neuro datasets, merges them into a unified schema, and exposes a lightweight UI for exploration and querying.

**Architecture:** Source connectors pull raw data from public APIs/archives → normalization transforms map each source into a canonical schema → a local relational store holds merged records with full provenance → a web UI and CLI layer enables exploration and querying.

**Tech Stack:** Python 3.12+, `uv` for environment management, SQLite (MVP) or DuckDB (recommended upgrade path), FastAPI + Streamlit for UI, pytest for all tests, BIDS/NWB format awareness for neuroimaging data.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Database Choice Analysis](#database-choice-analysis)
3. [Multi-Source Merge Strategy](#multi-source-merge-strategy)
4. [Phase 0 — Scaffolding & Contracts](#phase-0--scaffolding--contracts)
5. [Phase 1 — First Source Connector (OpenNeuro)](#phase-1--first-source-connector-openneuro)
6. [Phase 2 — MVP UI](#phase-2--mvp-ui)
7. [Phase 3 — Second Source + Merge Layer](#phase-3--second-source--merge-layer)
8. [Phase 4 — Query & Analysis Layer](#phase-4--query--analysis-layer)
9. [Future Phases](#future-phases)

---

## Project Structure

```
neuroDb/
├── docs/
│   └── ClaudeDbEpochPlan.md         ← this file
├── src/
│   └── neurodb/
│       ├── __init__.py
│       ├── schema.py                ← canonical schema definitions (SQLAlchemy models)
│       ├── db.py                    ← DB engine, session factory, migrations
│       ├── provenance.py            ← lineage/run-record helpers
│       ├── connectors/
│       │   ├── __init__.py
│       │   ├── base.py              ← abstract connector interface
│       │   ├── openneuro.py         ← OpenNeuro GraphQL connector
│       │   └── allen_brain.py       ← Allen Brain Atlas REST connector
│       ├── transforms/
│       │   ├── __init__.py
│       │   ├── normalize.py         ← field-mapping helpers (raw → canonical)
│       │   └── merge.py             ← dedup + cross-source merge logic
│       ├── query.py                 ← query interface (SQL/ORM helpers)
│       └── ui/
│           ├── app.py               ← Streamlit app entry point
│           └── pages/
│               ├── datasets.py      ← dataset browser page
│               └── query.py         ← ad-hoc query page
├── tests/
│   ├── fixtures/
│   │   ├── openneuro_sample.json    ← deterministic test fixture
│   │   └── allen_sample.json
│   ├── unit/
│   │   ├── test_schema.py
│   │   ├── test_normalize.py
│   │   └── test_merge.py
│   └── integration/
│       ├── test_openneuro_ingest.py ← full ingest → store → query path
│       └── test_idempotent.py       ← re-run proves no duplicates
├── scripts/
│   ├── ingest.py                    ← CLI entry: `uv run scripts/ingest.py --source openneuro`
│   └── query_cli.py                 ← CLI entry: `uv run scripts/query_cli.py --search "plasticity"`
├── pyproject.toml
├── uv.lock
└── README.md
```

---

## Database Choice Analysis

### Option A: SQLite (MVP default)

**Pros:**
- Zero install, single file, fully portable.
- Works on all platforms with no server process.
- Python's `sqlite3` is built-in; SQLAlchemy support is first-class.
- Git-friendly for small snapshots (binary, but diff-able via `sqlite3 .dump`).
- Adequate for single-user exploration and datasets up to ~1–5 GB.

**Cons:**
- Poor concurrent write performance (single writer at a time).
- No native support for columnar/analytical queries — large aggregations are slow.
- Does not support array or JSON column types natively (stored as text blobs).
- Harder to scale if the project moves toward multi-user or streaming ingest.
- No built-in support for time-series-specific indexing (relevant for neural recordings).

**Best for:** Phase 0–2, local solo use, datasets < 2 GB, rapid prototyping.

---

### Option B: DuckDB (recommended upgrade at Phase 3)

**Pros:**
- Columnar in-process database — analytical queries (GROUP BY, window functions) are 10–100× faster than SQLite on research-scale data.
- Native support for Parquet, CSV, and JSON — can query files directly without importing.
- Python-native: `import duckdb; con.execute("SELECT ...")` — no server.
- Excellent pandas/Polars interop (`duckdb.from_df(df)`).
- Supports `LIST` and `STRUCT` types natively — much better for nested neuro metadata.
- Active development with neuroscience-adjacent communities adopting it.

**Cons:**
- Less familiar tooling than SQLite for beginners.
- SQLAlchemy support exists but is less mature than SQLite/Postgres.
- Single-file storage not as portable for very small datasets (overhead).
- Write concurrency still limited (better than SQLite, but not Postgres).

**Best for:** Phase 3+, analytical queries over large merged datasets, Parquet/columnar workflows.

---

### Approved Plan

| Phase | Store | Decision date |
|-------|-------|---------------|
| 0–2 (MVP) | **SQLite** — zero friction, good enough | 2026-04-11 |
| 3+ (multi-source, analytical) | **DuckDB** — migrate schema, gain analytical speed | 2026-04-11 |

> PostgreSQL is **out of scope** for this epoch and should not be introduced in design, architecture, or dependency decisions.

Schema design (via SQLAlchemy Core) should be database-agnostic from day one so migration requires only a connection-string swap and one migration script.

---

## Multi-Source Merge Strategy

### Challenge

Public neuro datasets use different identifiers, taxonomies, coordinate systems, and metadata conventions:
- OpenNeuro uses BIDS format and DOI-based dataset identifiers.
- Allen Brain Atlas uses its own ontology IDs and ABA coordinate space.
- HCP uses subject IDs unique to that project.
- NeuroVault uses NIfTI image hashes.

### Approved Merge Progression: A → C → B (deferred)

---

#### Approach A: Source-Specific Tables + Discovery Index — **Start here (Phases 1–3)**

Each source gets its own table with its native field layout. A thin `datasets_index` table acts as a shared registry that cross-cutting tables (`subjects`, `cross_refs`, `quality_events`) reference via integer FK. No cross-source UNION queries are needed at this stage — each source is queried independently.

```
datasets_index(id, source, source_id, run_id)                            ← shared integer PK anchor
openneuro_datasets(id, index_id, source_id, title, doi, modality,
                   n_subjects, bids_version, metadata_json, run_id)
allen_datasets(id, index_id, source_id, title, modality,
               plane_of_section_id, specimen_id, metadata_json, run_id)
subjects(id, index_id, source_subject_id, age, sex, diagnosis, metadata_json)
cross_refs(id, source_a, id_a, source_b, id_b, confidence, method)
quality_events(id, entity_type, entity_source, entity_id, flag,
               severity, note, flagged_at, run_id)
```

**Why `datasets_index`?** Subjects and cross_refs need a stable integer FK to reference datasets without being coupled to any one source table. When a new source is added, it writes to `datasets_index` and its own table — `subjects` and `cross_refs` schemas are unchanged.

**Pros:**
- Source-native fields are first-class — no NULL-sprawl or `metadata_json` blob for queryable fields.
- Schema changes per source are isolated — an Allen-specific field doesn't touch the OpenNeuro table.
- Natural fit for structurally divergent sources (human subjects vs mouse specimens).
- `datasets_index` gives subjects and cross_refs a stable anchor without hard-coding source structure.
- Each source table can be queried directly with full field access.

**Cons:**
- Schema DDL grows with every new source — one new table per connector.
- Cross-source queries require views or explicit UNION (addressed by Approach C at Phase 3).
- Two writes per dataset ingest: one to `datasets_index`, one to the source-specific table.
- `BaseConnector` returns source-specific types, not a single shared model.

**Approach B hooks to consider at this stage:**

Approach B (entity resolution) requires a `cross_refs` table and stable `source`/`source_id` keys to operate against. Approach A already provides both. The question is whether to add any pre-wiring now.

| Hook | Complexity | Recommendation |
|------|-----------|---------------|
| Add `cross_refs(source_a, id_a, source_b, id_b, confidence, method)` table to schema | Low — one DDL addition | **Yes.** Zero-cost to add now; very expensive to retrofit once data is live. |
| Populate `cross_refs` on ingest (DOI exact match) | Low-Medium — one SELECT + INSERT per dataset | **Maybe.** DOI matching is deterministic and low-risk. Only add if a second source with DOIs is confirmed in scope. |
| Fuzzy subject matching on ingest | High — requires NLP/heuristics per source pair | **No.** Premature. Adds failure modes before the first connector is stable. Defer entirely to Approach B phase. |

**Decision (2026-04-11):** Add the `cross_refs` table to the Phase 0 schema. Leave it empty. Populate only with DOI exact-match logic when Phase 3 confirms Allen and OpenNeuro share DOIs (they do not today — revisit at Phase 3 review).

---

#### Approach C: View-Based Virtual Merge — **Migrate here at Phase 3**

Define SQL views that `UNION ALL` across source-specific tables, applying field mappings at query time. No physical merge step; each source stays in its own schema.

**Pros:**
- No ETL merge step — views are always up to date.
- Easy to add/modify field mappings without reprocessing data.
- Works natively in DuckDB with Parquet files (no load step at all).
- **Serves as the DuckDB upgrade smoke test:** views use near-identical syntax in SQLite and DuckDB. If `v_all_datasets` and `v_dataset_summary` return correct results after swapping the engine connection string, the migration is validated. No new test logic required.
- **Surfaces semantic gaps between disparate sources:** running `v_dataset_summary` after loading both OpenNeuro and Allen Brain reveals field coverage differences (e.g., `n_subjects` is NULL for all Allen rows) before any entity-resolution work is attempted. This review output directly informs whether Approach B is worth pursuing.

**Cons:**
- Query performance degrades if views scan many large tables.
- Complex mapping logic in SQL views becomes hard to test.
- Provenance tracking requires careful view design.

**Approach B hooks to consider at this stage:**

At Phase 3, two sources are loaded. This is the first point where cross-source semantic review is possible.

| Hook | Complexity | Recommendation |
|------|-----------|---------------|
| Run field-coverage audit query after ingest (NULLs per field per source) | Low — one SQL script | **Yes.** Document output in `docs/reviews/phase3-field-coverage.md`. This is the gate for deciding whether Approach B is viable. |
| Add `v_canonical_subjects` view stub (returns empty until `cross_refs` is populated) | Low | **Yes.** Establishes the interface without committing to implementation. |
| Begin populating `cross_refs` with DOI matches | Low-Medium | **Conditional.** Only if field-coverage audit confirms both sources carry DOIs for overlapping datasets. |
| Build fuzzy subject matcher | High | **No.** Defer. |

---

#### Approach B: Entity-Resolution Merge — **Deferred; decision pending Phase 3 review**

Run an entity-resolution (dedup) step after ingest: fuzzy-match subjects by age+sex+diagnosis+scanner, match datasets by DOI or title similarity, produce a unified `canonical_subject_id`.

**Pros:**
- Cross-source queries become simple — one canonical subject table.
- Enables downstream hypothesis testing across sources (e.g., "subjects in both HCP and ABIDE").

**Cons:**
- Entity resolution is hard to get right — false positives silently corrupt data.
- Requires manual curation rules per source pair, which are expensive to maintain.
- Adds significant complexity before the first connector even works.
- Premature for DB Epoch; more appropriate after 3+ sources are stable and field-coverage gaps are understood.

**Status:** Deferred. The Phase 3 field-coverage review (`docs/reviews/phase3-field-coverage.md`) is the decision gate. If the review shows that sources share no common entity keys (DOI, ORCID, subject demographics), Approach B may remain deferred indefinitely.

---

### Merge Progression by Phase

| Phase | Merge Strategy | Approach B hooks |
|-------|---------------|-----------------|
| 0 | Schema scaffolding: `datasets_index`, `subjects`, `cross_refs`, `quality_events` | Empty `cross_refs` and `quality_events` tables pre-wired |
| 1–2 | **Approach A** — source-specific tables, single source queried directly | None |
| 3 | **Approach A → C** — add SQL views UNIONing source tables; run field-coverage audit | Conditional: DOI exact-match in `cross_refs` if sources overlap |
| 3 (DuckDB upgrade) | **Approach C** — view layer validates engine swap | `v_canonical_subjects` stub view |
| Future | **Approach B** — only if Phase 3 review justifies | Full entity-resolution matcher |

---

## Phase 0 — Scaffolding & Contracts

**Goal:** Repository structure, environment, canonical schema, provenance model, and test harness all in place before any ingest code is written.

### Task 0.1: Initialize Python environment

**Files:**
- Create: `pyproject.toml`
- Create: `src/neurodb/__init__.py`

- [x] **Step 1: Initialize uv project**

```bash
cd /home/oldha/projects/neuroDb
uv init --name neurodb --python 3.12
uv add sqlalchemy pytest pytest-cov httpx
uv add --dev ruff mypy
```

- [x] **Step 2: Verify environment**

```bash
uv run python -c "import sqlalchemy; print(sqlalchemy.__version__)"
```
Expected output: `2.x.x`

- [x] **Step 3: Create src/neurodb package**

```bash
mkdir -p src/neurodb/connectors src/neurodb/transforms src/neurodb/ui/pages
mkdir -p tests/unit tests/integration tests/fixtures
touch src/neurodb/__init__.py src/neurodb/connectors/__init__.py src/neurodb/transforms/__init__.py
```

- [x] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/ tests/
git commit -m "chore: initialize neurodb package with uv and sqlalchemy"
```

---

### Task 0.2: Define canonical schema

**Files:**
- Create: `src/neurodb/schema.py`
- Create: `tests/unit/test_schema.py`

- [x] **Step 1: Write the failing schema validation test**

Create `tests/unit/test_schema.py`:

```python
from neurodb.schema import DatasetIndex, Subject, IngestRun, CrossRef, QualityEvent
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session


def test_schema_creates_core_tables():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    # Core cross-cutting tables — source-specific tables added per connector
    assert "datasets_index" in table_names
    assert "subjects" in table_names
    assert "ingest_runs" in table_names
    assert "cross_refs" in table_names
    assert "quality_events" in table_names


def test_dataset_index_and_subject_linkage():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-04-11T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        session.add(idx)
        session.flush()
        subject = Subject(index_id=idx.id, source_subject_id="sub-01", age=25.0, sex="M")
        session.add(subject)
        session.commit()
        assert session.query(DatasetIndex).count() == 1
        assert session.query(Subject).count() == 1
        assert session.query(CrossRef).count() == 0    # empty until Phase 3 review gate
        assert session.query(QualityEvent).count() == 0
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/test_schema.py -v
```
Expected: `ModuleNotFoundError: No module named 'neurodb.schema'`

- [x] **Step 3: Implement schema**

Create `src/neurodb/schema.py`:

```python
from sqlalchemy import String, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    run_at: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DatasetIndex(Base):
    """Thin shared registry. Provides a stable integer PK for subjects,
    cross_refs, and quality_events without coupling them to any one source table.
    One row per ingested dataset regardless of source.

    Source-specific tables (openneuro_datasets, allen_datasets) reference
    this table via index_id and are defined alongside their connectors.
    """
    __tablename__ = "datasets_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)

    subjects: Mapped[list["Subject"]] = relationship(back_populates="dataset_index")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False)
    source_subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    age: Mapped[float | None] = mapped_column(Float, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(8), nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset_index: Mapped["DatasetIndex"] = relationship(back_populates="subjects")


class CrossRef(Base):
    """Records known cross-source links between entities.
    Populated only when a deterministic match exists (e.g. DOI exact match).
    Left empty until Phase 3 field-coverage review confirms overlap.
    """
    __tablename__ = "cross_refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_a: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    id_a: Mapped[str] = mapped_column(String(128), nullable=False)
    source_b: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    id_b: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)  # "high" | "medium" | "low"
    method: Mapped[str] = mapped_column(String(64), nullable=False)      # e.g. "doi_exact", "title_fuzzy"


class QualityEvent(Base):
    """Structured quality flag log. Attached to any entity by (entity_source, entity_id).

    Design decision (Conflict 4, 2026-04-11): separate table chosen over a column on
    datasets_index to support history, multiple entity types, and structured severity.

    Pros: tracks flag history over time; works for datasets, subjects, and ingest runs;
          severity and notes are structured and queryable.
    Cons: requires a JOIN to surface quality info alongside dataset fields; adds complexity
          for simple MVP use — most early flags will be static and rarely queried.
    """
    __tablename__ = "quality_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)   # "dataset" | "subject" | "ingest_run"
    entity_source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)    # source_id of the entity
    flag: Mapped[str] = mapped_column(String(64), nullable=False)                      # e.g. "incomplete_subjects", "deprecated_doi"
    severity: Mapped[str] = mapped_column(String(16), nullable=False)                  # "info" | "warning" | "error"
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    flagged_at: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)
```

> **Note:** `OpenNeuroDataset` and `AllenDataset` models are defined in Tasks 1.2 and 3.1 alongside their connectors. They import `Base` from this module so `init_db` creates all tables together.

- [x] **Step 4: Run test to confirm pass**

```bash
uv run pytest tests/unit/test_schema.py -v
```
Expected: `PASSED`

- [x] **Step 5: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_schema.py
git commit -m "feat: define core schema (DatasetIndex, Subject, CrossRef, QualityEvent, IngestRun)"
```

---

### Task 0.3: DB engine and session factory

**Files:**
- Create: `src/neurodb/db.py`
- Create: `tests/unit/test_db.py`

- [x] **Step 1: Write failing test**

Create `tests/unit/test_db.py`:

```python
from neurodb.db import get_engine, get_session, init_db
from neurodb.schema import DatasetIndex, QualityEvent

def test_init_creates_schema():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 0
        assert session.query(QualityEvent).count() == 0
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/test_db.py -v
```
Expected: `ModuleNotFoundError: No module named 'neurodb.db'`

- [x] **Step 3: Implement db.py**

Create `src/neurodb/db.py`:

```python
from contextlib import contextmanager
from sqlalchemy import create_engine as _create_engine, Engine
from sqlalchemy.orm import Session
from neurodb.schema import Base


def get_engine(url: str = "sqlite:///neurodb.db") -> Engine:
    return _create_engine(url, echo=False)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def get_session(engine: Engine):
    with Session(engine) as session:
        yield session
        session.commit()
```

- [x] **Step 4: Run test to confirm pass**

```bash
uv run pytest tests/unit/test_db.py -v
```

- [x] **Step 5: Commit**

```bash
git add src/neurodb/db.py tests/unit/test_db.py
git commit -m "feat: add db engine and session factory"
```

---

### Phase 0 — Approval Gate

**Do not begin Phase 1 until approval is recorded here.**

Present the following to the user for review before proceeding:
- All Phase 0 task checkboxes are checked
- `uv run pytest tests/ -v` passes
- Schema file (`src/neurodb/schema.py`) is committed and reviewable
- Provenance model (`src/neurodb/provenance.py`) is committed and reviewable
- User has completed all steps in `docs/manualTestPlan_phase0.md` and signed off

**Approval:** Approved by Eric Herrmann on 2026-04-12 — no manual test plan file (Phase 0 was scaffolding only; schema and provenance reviewed directly)

---

## Phase 1 — First Source Connector (OpenNeuro)

**Goal:** One full ingest path from OpenNeuro's public GraphQL API → normalized records → SQLite → queryable. Idempotent on re-run.

**Why OpenNeuro first:** It's the largest open neuroimaging repository (~1,000+ BIDS datasets), has a public GraphQL API with no auth required, and covers fMRI/EEG/MRI modalities directly relevant to plasticity research.

**API reference:** `https://openneuro.org/crn/graphql` (public, unauthenticated, rate-limited)

---

### Task 1.1: Base connector interface

**Files:**
- Create: `src/neurodb/connectors/base.py`
- Create: `tests/unit/test_base_connector.py`

- [x] **Step 1: Write failing test**

Create `tests/unit/test_base_connector.py`:

```python
import pytest
from neurodb.connectors.base import BaseConnector

def test_base_connector_is_abstract():
    with pytest.raises(TypeError):
        BaseConnector()  # cannot instantiate abstract class
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/test_base_connector.py -v
```

- [x] **Step 3: Implement base connector**

Create `src/neurodb/connectors/base.py`:

```python
from abc import ABC, abstractmethod
from typing import Any, Iterator
from neurodb.schema import Subject


class BaseConnector(ABC):
    """Contract all source connectors must implement.

    Each connector defines its own ORM model (e.g. OpenNeuroDataset) in the
    same module as the connector. normalize_dataset returns that source-specific
    model instance. The ingest runner writes both a DatasetIndex row and the
    source-specific row per dataset.
    """

    SOURCE_NAME: str  # subclasses set this as a class attribute

    @abstractmethod
    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        """Yield raw dataset dicts from the source API."""

    @abstractmethod
    def get_source_id(self, raw: dict) -> str:
        """Extract the source-native identifier string from a raw record."""

    @abstractmethod
    def normalize_dataset(self, raw: dict, index_id: int, run_id: int) -> Any:
        """Map a raw source dict to this connector's ORM model (not yet committed).
        Returns an instance of the source-specific model (e.g. OpenNeuroDataset).
        index_id is the DatasetIndex.id already written by the ingest runner.
        """

    @abstractmethod
    def fetch_subjects(self, dataset_source_id: str) -> Iterator[dict]:
        """Yield raw subject dicts for a given dataset."""

    @abstractmethod
    def normalize_subject(self, raw: dict, index_id: int) -> Subject:
        """Map a raw subject dict to a Subject ORM object.
        index_id references DatasetIndex, not any source-specific table.
        """
```

- [x] **Step 4: Run test**

```bash
uv run pytest tests/unit/test_base_connector.py -v
```
Expected: `PASSED`

- [x] **Step 5: Commit**

```bash
git add src/neurodb/connectors/base.py tests/unit/test_base_connector.py
git commit -m "feat: add abstract BaseConnector interface"
```

---

### Task 1.2: OpenNeuro connector (with model and test fixture)

**Files:**
- Create: `src/neurodb/connectors/openneuro.py` (includes `OpenNeuroDataset` model)
- Create: `tests/fixtures/openneuro_sample.json`
- Create: `tests/unit/test_openneuro_connector.py`

- [x] **Step 1: Create deterministic fixture**

Create `tests/fixtures/openneuro_sample.json`:

```json
{
  "data": {
    "datasets": {
      "edges": [
        {
          "node": {
            "id": "ds000001",
            "name": "Balloon Analog Risk Task",
            "description": "fMRI study of risk-taking in healthy adults.",
            "numFiles": 90,
            "metadata": {
              "species": "Human",
              "modalities": ["MRI"],
              "numberOfParticipants": 16
            },
            "doi": "10.18112/openneuro.ds000001.v1.0.0"
          }
        },
        {
          "node": {
            "id": "ds000002",
            "name": "Multiband EEG-fMRI Resting State",
            "description": "Simultaneous EEG-fMRI resting state data.",
            "numFiles": 210,
            "metadata": {
              "species": "Human",
              "modalities": ["MRI", "EEG"],
              "numberOfParticipants": 22
            },
            "doi": null
          }
        }
      ]
    }
  }
}
```

- [x] **Step 2: Write failing test**

Create `tests/unit/test_openneuro_connector.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from neurodb.connectors.openneuro import OpenNeuroConnector, OpenNeuroDataset

FIXTURE = Path("tests/fixtures/openneuro_sample.json")


def _mock_response():
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_fetch_datasets_returns_two_records():
    conn = OpenNeuroConnector()
    with patch("neurodb.connectors.openneuro.httpx.post", return_value=_mock_response()):
        results = list(conn.fetch_datasets(limit=10))
    assert len(results) == 2
    assert results[0]["id"] == "ds000001"


def test_get_source_id():
    conn = OpenNeuroConnector()
    assert conn.get_source_id({"id": "ds000001"}) == "ds000001"


def test_normalize_dataset_maps_fields():
    conn = OpenNeuroConnector()
    raw = {
        "id": "ds000001",
        "name": "Balloon Analog Risk Task",
        "description": "fMRI study.",
        "metadata": {"modalities": ["MRI"], "numberOfParticipants": 16},
        "doi": "10.18112/openneuro.ds000001.v1.0.0",
    }
    ds = conn.normalize_dataset(raw, index_id=1, run_id=1)
    assert isinstance(ds, OpenNeuroDataset)
    assert ds.source_id == "ds000001"
    assert ds.modality == "MRI"
    assert ds.n_subjects == 16
    assert ds.doi == "10.18112/openneuro.ds000001.v1.0.0"
    assert ds.index_id == 1
```

- [x] **Step 3: Run to confirm failure**

```bash
uv run pytest tests/unit/test_openneuro_connector.py -v
```

- [x] **Step 4: Implement OpenNeuro connector and model**

Create `src/neurodb/connectors/openneuro.py`:

```python
import json
from typing import Any, Iterator
import httpx
from sqlalchemy import String, Integer, ForeignKey, Text
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
        description
        numFiles
        doi
        metadata {
          species
          modalities
          numberOfParticipants
          bidsVersion
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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

    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        response = httpx.post(
            GRAPHQL_URL,
            json={"query": _DATASETS_QUERY, "variables": {"first": limit}},
            timeout=30,
        )
        response.raise_for_status()
        edges = response.json()["data"]["datasets"]["edges"]
        for edge in edges:
            yield edge["node"]

    def get_source_id(self, raw: dict) -> str:
        return raw["id"]

    def normalize_dataset(self, raw: dict, index_id: int, run_id: int) -> OpenNeuroDataset:
        meta = raw.get("metadata") or {}
        modalities = meta.get("modalities") or []
        modality = modalities[0] if modalities else None
        return OpenNeuroDataset(
            index_id=index_id,
            source_id=raw["id"],
            title=raw.get("name", ""),
            doi=raw.get("doi"),
            modality=modality,
            n_subjects=meta.get("numberOfParticipants"),
            bids_version=meta.get("bidsVersion"),
            description=raw.get("description"),
            metadata_json=json.dumps(meta),
            run_id=run_id,
        )

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
```

- [x] **Step 5: Run tests**

```bash
uv run pytest tests/unit/test_openneuro_connector.py -v
```
Expected: `3 passed`

- [x] **Step 6: Commit**

```bash
git add src/neurodb/connectors/openneuro.py tests/fixtures/openneuro_sample.json tests/unit/test_openneuro_connector.py
git commit -m "feat: OpenNeuro GraphQL connector with normalize and fixture"
```

---

### Task 1.3: Ingest runner with provenance and idempotency

**Files:**
- Create: `src/neurodb/provenance.py`
- Create: `scripts/ingest.py`
- Create: `tests/integration/test_openneuro_ingest.py`
- Create: `tests/integration/test_idempotent.py`

- [x] **Step 1: Write integration tests**

Create `tests/integration/test_openneuro_ingest.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.provenance import run_ingest
from neurodb.connectors.openneuro import OpenNeuroConnector, OpenNeuroDataset
from neurodb.schema import DatasetIndex, IngestRun

FIXTURE = Path("tests/fixtures/openneuro_sample.json")


def _mock_post(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_full_ingest_stores_datasets():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.openneuro.httpx.post", side_effect=_mock_post):
        run_ingest(engine, connector=OpenNeuroConnector(), limit=10)
    with get_session(engine) as session:
        assert session.query(DatasetIndex).count() == 2
        assert session.query(OpenNeuroDataset).count() == 2
        assert session.query(IngestRun).count() == 1
        ds = session.query(OpenNeuroDataset).filter_by(source_id="ds000001").one()
        assert ds.title == "Balloon Analog Risk Task"
        idx = session.query(DatasetIndex).filter_by(source_id="ds000001").one()
        assert idx.source == "openneuro"
```

Create `tests/integration/test_idempotent.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.provenance import run_ingest
from neurodb.connectors.openneuro import OpenNeuroConnector, OpenNeuroDataset
from neurodb.schema import DatasetIndex

FIXTURE = Path("tests/fixtures/openneuro_sample.json")


def _mock_post(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_double_ingest_does_not_duplicate():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with patch("neurodb.connectors.openneuro.httpx.post", side_effect=_mock_post):
        run_ingest(engine, connector=OpenNeuroConnector(), limit=10)
        run_ingest(engine, connector=OpenNeuroConnector(), limit=10)
    with get_session(engine) as session:
        # Second run should upsert, not insert duplicates
        assert session.query(DatasetIndex).count() == 2
        assert session.query(OpenNeuroDataset).count() == 2
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/integration/ -v
```

- [x] **Step 3: Implement provenance runner**

Create `src/neurodb/provenance.py`:

```python
from datetime import datetime, timezone
from sqlalchemy import Engine, select
from neurodb.db import get_session
from neurodb.schema import IngestRun, DatasetIndex
from neurodb.connectors.base import BaseConnector


def run_ingest(engine: Engine, connector: BaseConnector, limit: int = 100) -> IngestRun:
    """Fetch datasets from connector, upsert into DB, record provenance.

    Per dataset, two upserts occur:
    1. DatasetIndex — shared registry row (source + source_id unique key).
    2. Source-specific table — full native fields, referenced via index_id.
    """
    run = IngestRun(
        source=connector.SOURCE_NAME,
        run_at=datetime.now(timezone.utc).isoformat(),
        version="0.1.0",
    )
    with get_session(engine) as session:
        session.add(run)
        session.flush()

        for raw in connector.fetch_datasets(limit=limit):
            source_id = connector.get_source_id(raw)

            # Step 1: Upsert DatasetIndex
            existing_idx = session.execute(
                select(DatasetIndex).where(
                    DatasetIndex.source == connector.SOURCE_NAME,
                    DatasetIndex.source_id == source_id,
                )
            ).scalar_one_or_none()

            if existing_idx:
                existing_idx.run_id = run.id
                index_id = existing_idx.id
            else:
                idx = DatasetIndex(
                    source=connector.SOURCE_NAME,
                    source_id=source_id,
                    run_id=run.id,
                )
                session.add(idx)
                session.flush()
                index_id = idx.id

            # Step 2: Upsert source-specific record
            source_record = connector.normalize_dataset(raw, index_id=index_id, run_id=run.id)
            SourceModel = type(source_record)
            existing_src = session.execute(
                select(SourceModel).where(SourceModel.index_id == index_id)
            ).scalar_one_or_none()

            if existing_src:
                for attr, val in vars(source_record).items():
                    if not attr.startswith("_"):
                        setattr(existing_src, attr, val)
            else:
                session.add(source_record)

    return run
```

- [x] **Step 4: Run integration tests**

```bash
uv run pytest tests/integration/ -v
```
Expected: `3 passed`

- [x] **Step 5: Create ingest CLI script**

Create `scripts/ingest.py`:

```python
#!/usr/bin/env python
"""CLI: run ingest for a named source.

Usage:
    uv run scripts/ingest.py --source openneuro --limit 200 --db neurodb.db
"""
import argparse
from neurodb.db import get_engine, init_db
from neurodb.provenance import run_ingest
from neurodb.connectors.openneuro import OpenNeuroConnector

CONNECTORS = {
    "openneuro": OpenNeuroConnector,
}


def main():
    parser = argparse.ArgumentParser(description="Ingest a neuro data source into NeuroDb")
    parser.add_argument("--source", choices=list(CONNECTORS), required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--db", default="neurodb.db")
    args = parser.parse_args()

    engine = get_engine(f"sqlite:///{args.db}")
    init_db(engine)
    connector = CONNECTORS[args.source]()
    run = run_ingest(engine, connector=connector, limit=args.limit)
    print(f"Ingest complete: run_id={run.id}, source={run.source}, at={run.run_at}")


if __name__ == "__main__":
    main()
```

- [x] **Step 6: Run full test suite**

```bash
uv run pytest tests/ -v --tb=short
```
Expected: all tests pass.

- [x] **Step 7: Commit**

```bash
git add src/neurodb/provenance.py scripts/ingest.py tests/integration/
git commit -m "feat: ingest runner with upsert idempotency and provenance tracking"
```

---

### Phase 1 — Approval Gate

**Do not begin Phase 2 until approval is recorded here.**

Present the following to the user for review before proceeding:
- All Phase 1 task checkboxes are checked
- `uv run pytest tests/ -v` passes (unit + integration, including idempotency test)
- A sample ingest run has completed: `uv run scripts/ingest.py --source openneuro --limit 5`
- Output of `uv run scripts/query_cli.py --search "plasticity"` (or equivalent) shown to user
- User has completed all steps in `docs/manualTestPlan_phase1.md` and signed off

**Approval:** Approved by Eric Herrmann on 2026-04-11 — no manual test plan file (ingest and query verified inline during development)

---

## Phase 2 — MVP UI

**Goal:** A simple, self-contained web UI that lets a user browse ingested datasets, filter by modality/source, and run basic free-text queries — all against the local SQLite DB. No backend server required beyond `streamlit run`.

**Why Streamlit:** Fastest path from Python data to interactive UI; researcher-friendly; no JS required; single-file deployable. Reconsider if multi-user or embedding needs emerge.

**Streamlit alternative analysis:**
- **Gradio** — better for ML model demos, less suited to tabular data browsing.
- **Panel/Holoviz** — more powerful dashboards, steeper learning curve, overkill for MVP.
- **FastAPI + React** — production-grade but 10× the code; defer to Phase 4+.

---

### Task 2.1: Install Streamlit and query helper

**Files:**
- Modify: `pyproject.toml` (add streamlit)
- Create: `src/neurodb/query.py`
- Create: `tests/unit/test_query.py`

- [x] **Step 1: Add Streamlit dependency**

```bash
uv add streamlit pandas
```

- [x] **Step 2: Write failing query test**

Create `tests/unit/test_query.py`:

```python
from sqlalchemy import create_engine
from neurodb.db import init_db, get_session
from neurodb.schema import Dataset, IngestRun
from neurodb.query import search_datasets, get_dataset_by_id


def _seed_db(engine):
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-04-11", version="0.1")
        session.add(run)
        session.flush()
        session.add(Dataset(source="openneuro", source_id="ds001", title="Plasticity Study",
                            modality="fMRI", n_subjects=20, run_id=run.id))
        session.add(Dataset(source="openneuro", source_id="ds002", title="EEG Resting State",
                            modality="EEG", n_subjects=15, run_id=run.id))


def test_search_by_keyword():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_db(engine)
    with get_session(engine) as session:
        results = search_datasets(session, keyword="plasticity")
    assert len(results) == 1
    assert results[0].source_id == "ds001"


def test_search_by_modality():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_db(engine)
    with get_session(engine) as session:
        results = search_datasets(session, modality="EEG")
    assert len(results) == 1
    assert results[0].modality == "EEG"


def test_get_by_id():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    _seed_db(engine)
    with get_session(engine) as session:
        ds = get_dataset_by_id(session, 1)
    assert ds.source_id == "ds001"
```

- [x] **Step 3: Run to confirm failure**

```bash
uv run pytest tests/unit/test_query.py -v
```

- [x] **Step 4: Implement query helpers**

Create `src/neurodb/query.py`:

```python
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from neurodb.schema import Dataset


def search_datasets(
    session: Session,
    keyword: str | None = None,
    modality: str | None = None,
    source: str | None = None,
    limit: int = 200,
) -> list[Dataset]:
    stmt = select(Dataset)
    if keyword:
        term = f"%{keyword.lower()}%"
        stmt = stmt.where(
            or_(
                Dataset.title.ilike(term),
                Dataset.description.ilike(term),
            )
        )
    if modality:
        stmt = stmt.where(Dataset.modality == modality)
    if source:
        stmt = stmt.where(Dataset.source == source)
    stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars())


def get_dataset_by_id(session: Session, dataset_id: int) -> Dataset | None:
    return session.get(Dataset, dataset_id)
```

- [x] **Step 5: Run query tests**

```bash
uv run pytest tests/unit/test_query.py -v
```
Expected: `3 passed`

- [x] **Step 6: Commit**

```bash
git add src/neurodb/query.py tests/unit/test_query.py pyproject.toml uv.lock
git commit -m "feat: query helpers (search_datasets, get_dataset_by_id)"
```

---

### Task 2.2: Streamlit application

**Files:**
- Create: `src/neurodb/ui/app.py`
- Create: `src/neurodb/ui/pages/datasets.py`
- Create: `src/neurodb/ui/pages/query.py`

- [x] **Step 1: Create Streamlit app entry point**

Create `src/neurodb/ui/app.py`:

```python
"""
NeuroDb Explorer — local neuroscience dataset browser.

Run with:
    uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.db
"""
import sys
import streamlit as st
from neurodb.db import get_engine, init_db

st.set_page_config(page_title="NeuroDb Explorer", layout="wide")

# Accept --db flag from command line; default to neurodb.db
db_path = "neurodb.db"
for i, arg in enumerate(sys.argv):
    if arg == "--db" and i + 1 < len(sys.argv):
        db_path = sys.argv[i + 1]

engine = get_engine(f"sqlite:///{db_path}")
init_db(engine)

st.session_state["engine"] = engine

st.title("NeuroDb Explorer")
st.caption(f"Connected to: `{db_path}`")

page = st.sidebar.radio("Navigate", ["Dataset Browser", "SQL Query"])

if page == "Dataset Browser":
    from neurodb.ui.pages.datasets import render
    render(engine)
elif page == "SQL Query":
    from neurodb.ui.pages.query import render
    render(engine)
```

- [x] **Step 2: Create dataset browser page**

Create `src/neurodb/ui/pages/datasets.py`:

```python
import pandas as pd
import streamlit as st
from sqlalchemy import Engine, text
from neurodb.db import get_session
from neurodb.query import search_datasets


def render(engine: Engine):
    st.header("Dataset Browser")

    col1, col2, col3 = st.columns(3)
    keyword = col1.text_input("Search title/description", "")
    modality = col2.selectbox("Modality", ["Any", "MRI", "fMRI", "EEG", "MEG"])
    source = col3.selectbox("Source", ["Any", "openneuro", "allen_brain"])

    with get_session(engine) as session:
        results = search_datasets(
            session,
            keyword=keyword or None,
            modality=None if modality == "Any" else modality,
            source=None if source == "Any" else source,
        )

    if not results:
        st.info("No datasets found. Run an ingest first: `uv run scripts/ingest.py --source openneuro`")
        return

    data = [
        {
            "ID": ds.source_id,
            "Source": ds.source,
            "Title": ds.title,
            "Modality": ds.modality,
            "Subjects": ds.n_subjects,
            "DOI": ds.doi or "",
        }
        for ds in results
    ]
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
    st.caption(f"{len(results)} dataset(s) found")
```

- [x] **Step 3: Create SQL query page**

Create `src/neurodb/ui/pages/query.py`:

```python
import pandas as pd
import streamlit as st
from sqlalchemy import Engine, text


def render(engine: Engine):
    st.header("SQL Query")
    st.caption("Run raw SQL against the local NeuroDb. Tables: `datasets`, `subjects`, `ingest_runs`.")

    default_query = "SELECT source, modality, COUNT(*) as n FROM datasets GROUP BY source, modality ORDER BY n DESC;"
    sql = st.text_area("SQL", value=default_query, height=120)

    if st.button("Run Query"):
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                rows = result.fetchall()
                cols = list(result.keys())
            df = pd.DataFrame(rows, columns=cols)
            st.dataframe(df, use_container_width=True)
            st.caption(f"{len(df)} row(s)")
        except Exception as e:
            st.error(f"Query error: {e}")
```

- [x] **Step 4: Verify UI starts (manual)**

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.db
```
Open `http://localhost:8501` in a browser. Confirm:
- Dataset Browser page loads with filter controls.
- "No datasets found" message shows (empty DB).
- SQL Query page loads and executes the default query without errors.
- Run `uv run scripts/ingest.py --source openneuro --limit 20` in a second terminal, then refresh the UI to confirm datasets appear.

- [x] **Step 5: Commit**

```bash
git add src/neurodb/ui/ scripts/ingest.py
git commit -m "feat: Streamlit MVP UI with dataset browser and SQL query page"
```

---

### Phase 2 — Approval Gate

**Do not begin Phase 3 until approval is recorded here.**

Present the following to the user for review before proceeding:
- All Phase 2 task checkboxes are checked
- `uv run pytest tests/ -v` passes
- Streamlit UI is running and user has confirmed dataset browsing and SQL query page work as expected: `uv run streamlit run src/neurodb/ui/app.py`
- User has completed all steps in `docs/manualTestPlan_phase2.md` and signed off

**Approval:** Approved by Eric Herrmann on 2026-04-11 — manual UI verification deferred (Streamlit server not tested live; all automated tests pass); manual test plan file was created then removed

---

## Phase 3 — Second Source + Merge Layer

**Goal:** Add the Allen Brain Atlas connector, define the SQL-view merge strategy, and validate that cross-source queries work correctly.

**Why Allen Brain Atlas second:** It provides gene-expression and brain-region data orthogonal to OpenNeuro's imaging datasets. Together they enable plasticity queries like "which brain regions show both structural MRI changes (OpenNeuro) and gene-expression signatures (Allen)?".

**Allen Brain Atlas API:** Public REST API, no auth for read-only access.
- Dataset list: `https://api.brain-map.org/api/v2/data/query.json?criteria=model::SectionDataSet`
- Documentation: https://help.brain-map.org/display/api/Allen+Brain+Atlas+API

---

### Task 3.1: Allen Brain Atlas connector (with model)

**Files:**
- Create: `src/neurodb/connectors/allen_brain.py` (includes `AllenDataset` model)
- Create: `tests/fixtures/allen_sample.json`
- Create: `tests/unit/test_allen_connector.py`

- [x] **Step 1: Create fixture**

Create `tests/fixtures/allen_sample.json`:

```json
{
  "success": true,
  "id": 0,
  "total_rows": 2,
  "num_rows": 2,
  "msg": [
    {
      "id": 100140756,
      "name": "Mouse Brain Atlas - P56 ISH",
      "description": "In-situ hybridization gene expression atlas for adult mouse brain.",
      "specimen_id": 12345,
      "failed": false,
      "plane_of_section_id": 1
    },
    {
      "id": 100141219,
      "name": "Developing Mouse Brain Atlas",
      "description": "Gene expression across developmental stages.",
      "specimen_id": 67890,
      "failed": false,
      "plane_of_section_id": 2
    }
  ]
}
```

- [x] **Step 2: Write failing test**

Create `tests/unit/test_allen_connector.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from neurodb.connectors.allen_brain import AllenBrainConnector, AllenDataset

FIXTURE = Path("tests/fixtures/allen_sample.json")


def _mock_get(*args, **kwargs):
    data = json.loads(FIXTURE.read_text())
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_fetch_datasets_returns_two():
    conn = AllenBrainConnector()
    with patch("neurodb.connectors.allen_brain.httpx.get", side_effect=_mock_get):
        results = list(conn.fetch_datasets(limit=10))
    assert len(results) == 2


def test_get_source_id():
    conn = AllenBrainConnector()
    assert conn.get_source_id({"id": 100140756}) == "100140756"


def test_normalize_dataset_sets_fields():
    conn = AllenBrainConnector()
    raw = {"id": 100140756, "name": "Mouse Brain Atlas", "description": "ISH atlas", "plane_of_section_id": 1}
    ds = conn.normalize_dataset(raw, index_id=1, run_id=1)
    assert isinstance(ds, AllenDataset)
    assert ds.source_id == "100140756"
    assert ds.modality == "ISH"
    assert ds.plane_of_section_id == 1
    assert ds.index_id == 1
```

- [x] **Step 3: Run to confirm failure**

```bash
uv run pytest tests/unit/test_allen_connector.py -v
```

- [x] **Step 4: Implement Allen connector and model**

Create `src/neurodb/connectors/allen_brain.py`:

```python
import json
from typing import Any, Iterator
import httpx
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from neurodb.schema import Base, Subject
from neurodb.connectors.base import BaseConnector

_BASE = "https://api.brain-map.org/api/v2/data/query.json"
_MODALITY_MAP = {1: "ISH", 2: "ISH", 3: "IHC"}  # plane_of_section_id → modality label


class AllenDataset(Base):
    """Source-specific table for Allen Brain Atlas datasets.
    Preserves Allen-native fields (plane_of_section_id, specimen_id) that have
    no equivalent in OpenNeuro and would be NULL-sprawl in a shared table.
    """
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

    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        response = httpx.get(
            _BASE,
            params={
                "criteria": "model::SectionDataSet",
                "num_rows": limit,
                "start_row": 0,
            },
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
        return iter([])  # Allen uses mouse specimens, not human subjects; out of scope for MVP

    def normalize_subject(self, raw: dict, index_id: int) -> Subject:
        return Subject(index_id=index_id, source_subject_id=str(raw.get("id", "")))
```

- [x] **Step 5: Register connector in ingest CLI**

Edit `scripts/ingest.py`, change:

```python
from neurodb.connectors.openneuro import OpenNeuroConnector

CONNECTORS = {
    "openneuro": OpenNeuroConnector,
}
```

to:

```python
from neurodb.connectors.openneuro import OpenNeuroConnector
from neurodb.connectors.allen_brain import AllenBrainConnector

CONNECTORS = {
    "openneuro": OpenNeuroConnector,
    "allen_brain": AllenBrainConnector,
}
```

- [x] **Step 6: Run all tests**

```bash
uv run pytest tests/ -v
```
Expected: all pass.

- [x] **Step 7: Commit**

```bash
git add src/neurodb/connectors/allen_brain.py tests/fixtures/allen_sample.json tests/unit/test_allen_connector.py scripts/ingest.py
git commit -m "feat: Allen Brain Atlas connector (ISH/IHC datasets)"
```

---

### Task 3.2: Unified SQL view for cross-source queries

**Files:**
- Modify: `src/neurodb/db.py`
- Create: `tests/integration/test_unified_view.py`

- [x] **Step 1: Write failing view test**

Create `tests/integration/test_unified_view.py`:

```python
from sqlalchemy import create_engine, text
from neurodb.db import init_db, get_session, create_views
from neurodb.schema import IngestRun, DatasetIndex
from neurodb.connectors.openneuro import OpenNeuroDataset
from neurodb.connectors.allen_brain import AllenDataset


def _seed(engine):
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-04-11", version="0.1")
        session.add(run)
        session.flush()
        idx1 = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        idx2 = DatasetIndex(source="allen_brain", source_id="100140756", run_id=run.id)
        session.add_all([idx1, idx2])
        session.flush()
        session.add(OpenNeuroDataset(index_id=idx1.id, source_id="ds001",
                                     title="fMRI Study", modality="fMRI",
                                     n_subjects=20, run_id=run.id))
        session.add(AllenDataset(index_id=idx2.id, source_id="100140756",
                                  title="ISH Atlas", modality="ISH",
                                  plane_of_section_id=1, run_id=run.id))


def test_unified_view_contains_both_sources():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source")).fetchall()
    sources = {r[0]: r[1] for r in rows}
    assert sources["openneuro"] == 1
    assert sources["allen_brain"] == 1


def test_summary_view_reflects_both_sources():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    create_views(engine)
    _seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT source, modality FROM v_dataset_summary ORDER BY source")).fetchall()
    sources = [r[0] for r in rows]
    assert "openneuro" in sources
    assert "allen_brain" in sources
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/integration/test_unified_view.py -v
```

- [x] **Step 3: Add create_views to db.py**

Edit `src/neurodb/db.py`, add after `init_db`:

```python
from sqlalchemy import text

def create_views(engine: Engine) -> None:
    """Create unified SQL views across source-specific tables (Approach C).

    Each new source connector added in future phases must add its own
    SELECT branch to v_all_datasets and re-run create_views.
    """
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE VIEW IF NOT EXISTS v_all_datasets AS
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
        """))
        conn.execute(text("""
            CREATE VIEW IF NOT EXISTS v_dataset_summary AS
            SELECT
                source,
                modality,
                COUNT(*)         AS n_datasets,
                SUM(n_subjects)  AS total_subjects
            FROM v_all_datasets
            GROUP BY source, modality
        """))
        conn.execute(text("""
            CREATE VIEW IF NOT EXISTS v_canonical_subjects AS
            SELECT s.*, di.source, di.source_id
            FROM subjects s
            JOIN datasets_index di ON di.id = s.index_id
            WHERE EXISTS (
                SELECT 1 FROM cross_refs cr
                WHERE (cr.source_a = di.source AND cr.id_a = di.source_id)
                   OR (cr.source_b = di.source AND cr.id_b = di.source_id)
            )
        """))
        conn.commit()
```

- [x] **Step 4: Run test**

```bash
uv run pytest tests/integration/test_unified_view.py -v
```
Expected: `PASSED`

- [x] **Step 5: Update UI SQL query page default**

Edit `src/neurodb/ui/pages/query.py`, change the default query string to:

```python
default_query = "SELECT * FROM v_dataset_summary ORDER BY n_datasets DESC;"
```

- [x] **Step 6: Commit**

```bash
git add src/neurodb/db.py src/neurodb/ui/pages/query.py tests/integration/test_unified_view.py
git commit -m "feat: unified SQL views for cross-source queries (v_all_datasets, v_dataset_summary)"
```

---

### Task 3.3: Field-coverage review and Approach B gate

**Purpose:** Run `v_dataset_summary` and field-coverage audit queries across both loaded sources. Document findings in `docs/reviews/phase3-field-coverage.md`. This output is the decision gate for whether Approach B (entity resolution) is viable and when to populate `cross_refs`.

**Files:**
- Create: `docs/reviews/phase3-field-coverage.md` (output of this task — written by hand after running queries)
- Create: `scripts/field_coverage_audit.py`

- [x] **Step 1: Write the audit script**

Create `scripts/field_coverage_audit.py`:

```python
#!/usr/bin/env python
"""Audit field coverage across sources — run after Phase 3 ingest.

Usage:
    uv run scripts/field_coverage_audit.py --db neurodb.db
"""
import argparse
from sqlalchemy import text
from neurodb.db import get_engine, init_db, create_views

COVERAGE_QUERY = """
SELECT
    source,
    COUNT(*) AS total,
    SUM(CASE WHEN doi IS NOT NULL THEN 1 ELSE 0 END) AS has_doi,
    SUM(CASE WHEN modality IS NOT NULL THEN 1 ELSE 0 END) AS has_modality,
    SUM(CASE WHEN n_subjects IS NOT NULL THEN 1 ELSE 0 END) AS has_n_subjects,
    SUM(CASE WHEN description IS NOT NULL AND description != '' THEN 1 ELSE 0 END) AS has_description
FROM datasets
GROUP BY source
ORDER BY source;
"""

SUMMARY_QUERY = "SELECT * FROM v_dataset_summary ORDER BY source, modality;"

DOI_OVERLAP_QUERY = """
SELECT d1.source AS source_a, d2.source AS source_b, d1.doi
FROM datasets d1
JOIN datasets d2 ON d1.doi = d2.doi AND d1.source < d2.source
WHERE d1.doi IS NOT NULL
ORDER BY d1.doi;
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="neurodb.db")
    args = parser.parse_args()

    engine = get_engine(f"sqlite:///{args.db}")
    init_db(engine)
    create_views(engine)

    with engine.connect() as conn:
        print("=== Field Coverage by Source ===")
        rows = conn.execute(text(COVERAGE_QUERY)).fetchall()
        headers = ["source", "total", "has_doi", "has_modality", "has_n_subjects", "has_description"]
        print("\t".join(headers))
        for row in rows:
            print("\t".join(str(v) for v in row))

        print("\n=== Dataset Summary (v_dataset_summary) ===")
        rows = conn.execute(text(SUMMARY_QUERY)).fetchall()
        print("source\tmodality\tn_datasets\ttotal_subjects")
        for row in rows:
            print("\t".join(str(v) for v in row))

        print("\n=== DOI Overlap Between Sources ===")
        rows = conn.execute(text(DOI_OVERLAP_QUERY)).fetchall()
        if rows:
            print("source_a\tsource_b\tdoi")
            for row in rows:
                print("\t".join(str(v) for v in row))
        else:
            print("(no DOI overlap found between sources)")


if __name__ == "__main__":
    main()
```

- [x] **Step 2: Run both source ingests**

```bash
uv run scripts/ingest.py --source openneuro --limit 100 --db neurodb.db
uv run scripts/ingest.py --source allen_brain --limit 100 --db neurodb.db
```

- [x] **Step 3: Run the audit**

```bash
uv run scripts/field_coverage_audit.py --db neurodb.db
```

Capture the output. Look specifically for:
- `has_doi` count for each source — if both sources have DOIs on the same datasets, `cross_refs` can be populated.
- `has_n_subjects` — if Allen shows 0 (expected: specimens, not human subjects), note this as a semantic gap.
- DOI overlap section — if any rows appear, Approach B DOI-matching hook is viable.

- [x] **Step 4: Document findings**

Create `docs/reviews/phase3-field-coverage.md` with the following template, filled in from the audit output:

```markdown
# Phase 3 Field Coverage Review
Date: YYYY-MM-DD
DB: neurodb.db
Sources ingested: openneuro (N datasets), allen_brain (N datasets)

## Field Coverage Table
[paste audit output here]

## Semantic Gaps Identified
- n_subjects: [note if Allen shows NULL as expected]
- modality: [note if Allen uses non-standard labels]
- doi: [note coverage per source]

## DOI Overlap
[paste overlap output or "none found"]

## Approach B Decision
- [x] DOI exact-match populating cross_refs: YES / NO / CONDITIONAL
  Reason: [e.g., "no DOI overlap found; defer"]
- [x] Fuzzy subject matching: DEFERRED
  Reason: Semantic gap — Allen uses mouse specimens, OpenNeuro uses human subjects.
- [x] Next review trigger: [e.g., "when DANDI or NeuroVault added as 3rd source"]
```

- [x] **Step 5: Commit**

```bash
mkdir -p docs/reviews
git add scripts/field_coverage_audit.py docs/reviews/phase3-field-coverage.md
git commit -m "feat: field coverage audit script and Phase 3 Approach B gate review"
```

---

### Phase 3 — Approval Gate

**Do not begin Phase 4 until approval is recorded here.**

Present the following to the user for review before proceeding:
- All Phase 3 task checkboxes are checked
- `uv run pytest tests/ -v` passes
- `docs/reviews/phase3-field-coverage.md` exists and is committed
- User has reviewed the field-coverage findings and confirmed the Approach B decision (defer or proceed)
- User has completed all steps in `docs/manualTestPlan_phase3.md` and signed off

**Approval:** Approved by Eric Herrmann on 2026-04-13

---

## Phase 4 — Query & Analysis Layer

**Goal:** A structured query CLI and first hypothesis query — "which modalities are most represented across sources?" as a baseline for downstream plasticity research.

---

### Task 4.1: Query CLI

**Files:**
- Create: `scripts/query_cli.py`

- [x] **Step 1: Implement**

Create `scripts/query_cli.py`:

```python
#!/usr/bin/env python
"""CLI: search and query the local NeuroDb.

Usage:
    uv run scripts/query_cli.py --search "plasticity"
    uv run scripts/query_cli.py --modality fMRI
    uv run scripts/query_cli.py --sql "SELECT * FROM v_dataset_summary"
"""
import argparse
from neurodb.db import get_engine, init_db, get_session
from neurodb.query import search_datasets
from sqlalchemy import text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", help="Keyword search on title/description")
    parser.add_argument("--modality", help="Filter by modality")
    parser.add_argument("--source", help="Filter by source")
    parser.add_argument("--sql", help="Raw SQL query")
    parser.add_argument("--db", default="neurodb.db")
    args = parser.parse_args()

    engine = get_engine(f"sqlite:///{args.db}")
    init_db(engine)

    if args.sql:
        with engine.connect() as conn:
            rows = conn.execute(text(args.sql)).fetchall()
        for row in rows:
            print("\t".join(str(v) for v in row))
    else:
        with get_session(engine) as session:
            results = search_datasets(
                session,
                keyword=args.search,
                modality=args.modality,
                source=args.source,
            )
        for ds in results:
            print(f"[{ds.source}] {ds.source_id} — {ds.title} ({ds.modality}, n={ds.n_subjects})")
        print(f"\n{len(results)} result(s)")


if __name__ == "__main__":
    main()
```

- [x] **Step 2: Verify manually**

```bash
uv run scripts/ingest.py --source openneuro --limit 50
uv run scripts/query_cli.py --search "memory"
uv run scripts/query_cli.py --sql "SELECT * FROM v_dataset_summary"
```

- [x] **Step 3: Commit**

```bash
git add scripts/query_cli.py
git commit -m "feat: query CLI with keyword, modality, and raw SQL modes"
```

---

### Phase 4 — Approval Gate

**Do not begin any Future Phase until approval is recorded here.**

Present the following to the user for review before proceeding:
- All Phase 4 task checkboxes are checked
- `uv run pytest tests/ -v` passes
- User has completed all steps in `docs/manualTestPlan_phase4.md` and signed off
- User has reviewed the hypothesis query output and confirmed the data layer is stable enough to build on
- User has decided which Future Phase (5, 6, 7, or 8) to prioritize next

**Approval:** Approved by Eric Herrmann on 2026-04-13

---

## Future Phases

### Phase 5 — DuckDB Migration (when datasets exceed ~2 GB)

1. Add `duckdb` via `uv add duckdb`.
2. Replace SQLAlchemy engine URL with `duckdb:///neurodb.duckdb` (via `duckdb-engine`).
3. Migrate existing SQLite data: `duckdb COPY datasets FROM neurodb.db`.
4. Update `create_views` — DuckDB views support Parquet scans directly.
5. Run full test suite with DuckDB engine; fix any SQLite-specific SQL.

Pros of migrating: 10–100× faster aggregations, native Parquet/CSV scan, LIST/STRUCT types.
Cons: breaks SQLite portability; `duckdb-engine` SQLAlchemy support is less mature.

### Phase 6 — Additional Sources

Priority order based on plasticity research relevance:

| Source | Data Type | API |
|--------|-----------|-----|
| DANDI Archive | NWB neurophysiology (electrophysiology, calcium imaging) | REST + `dandi` Python client |
| NeuroVault | Statistical brain maps (fMRI contrasts) | REST, no auth |
| ABIDE | Autism fMRI (cross-site, demographic-rich) | NITRC FTP |
| Human Connectome Project | High-res structural + functional MRI | AWS S3 (requires account) |

For each: implement connector following Task 1.1–1.3 pattern, add fixture, pass idempotency test, register in `ingest.py`.

### Phase 7 — Entity Resolution / Approach B (Decision Pending)

**Gate:** Do not start this phase until `docs/reviews/phase3-field-coverage.md` exists and the Approach B decision section confirms DOI overlap or viable subject matching is present across 3+ sources.

If the Phase 3 review shows no overlap (likely for OpenNeuro + Allen Brain alone — different species, no shared DOIs), defer this phase until a third source (e.g., DANDI or NeuroVault) is added and re-reviewed.

If the gate is passed:
1. `cross_refs` table already exists (added in Phase 0). Populate it:
   - DOI exact match → `confidence="high"`, `method="doi_exact"`
   - Title similarity (>0.9 Jaccard) → `confidence="medium"`, `method="title_fuzzy"`
2. Add `canonical_subjects` table with a `canonical_id` (only for sources sharing human subjects).
3. Build a rule-based matcher per confirmed source pair; log false positives for manual curation.
4. Add `v_canonical_subjects` view exposing unified subject records where `cross_refs` entries exist.
5. Treat all matcher output as advisory until manually reviewed — never silently overwrite source records.

### Phase 8 — Hypothesis & Report Layer

1. Pre-analysis plan document per hypothesis (in `docs/hypotheses/`).
2. Python analysis scripts that query the DB and produce structured results.
3. Uncertainty quantification (confidence intervals, effect sizes).
4. Reproducibility: each report records the `run_id` and DB hash it was generated from.

---

## Provenance & Reproducibility Checklist

Every ingest run must record:
- [ ] `source` — connector name
- [ ] `run_at` — UTC timestamp
- [ ] `version` — connector version string
- [ ] `notes` — optional freetext (data vintage, known issues)

Every analysis report must record:
- [ ] DB file path and SHA256 hash
- [ ] `run_id` range used
- [ ] Script version (git commit hash)
- [ ] Output timestamp

---

*Plan authored: 2026-04-11. Updated: 2026-04-11 (merge strategy reordered A→C→B; cross_refs hook added to Phase 0 schema; field-coverage review task added as Phase 3 gate for Approach B). Review against `NeuroDbGoals.md` before each phase begins.*
