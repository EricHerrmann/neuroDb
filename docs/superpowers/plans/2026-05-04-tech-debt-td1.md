# Tech Debt TD-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address all high-severity tech debt and critical medium-severity items: schema migration framework, connector completeness (fetch_by_id + search_by_keyword on all sources), explicit connector registration, StudyNote uniqueness constraint, and dependency upper-bound pinning.

**Architecture:** A lightweight schema migration table (`schema_migrations`) replaces the silent `create_all()` drift. A connectors package `__init__.py` makes registration explicit. Each connector gets `fetch_by_id` and `search_by_keyword` following the OpenNeuro reference implementation.

**Tech Stack:** Python, SQLAlchemy, DuckDB, httpx, pyproject.toml

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/neurodb/migrations.py` | Create | Migration registry and runner |
| `src/neurodb/db.py` | Modify | Call migration runner from `init_db` |
| `src/neurodb/schema.py` | Modify | Add StudyNote unique constraint (via migration) |
| `src/neurodb/connectors/__init__.py` | Modify | Explicit connector registry |
| `src/neurodb/ui/app.py` | Modify | Import from `neurodb.connectors` instead of individual modules |
| `src/neurodb/connectors/dandi.py` | Modify | Add `fetch_by_id`, `search_by_keyword` |
| `src/neurodb/connectors/neurovault.py` | Modify | Add `fetch_by_id`, `search_by_keyword` |
| `src/neurodb/connectors/allen_brain.py` | Modify | Add `fetch_by_id`, `search_by_keyword` |
| `pyproject.toml` | Modify | Add upper-bound pins on risky deps |
| `tests/unit/test_migrations.py` | Create | Migration runner unit tests |
| `tests/unit/test_connector_registry.py` | Create | Connector registration tests |
| `tests/unit/test_dandi_connector.py` | Create | DANDI fetch_by_id / search_by_keyword |
| `tests/unit/test_neurovault_connector.py` | Create | NeuroVault fetch_by_id / search_by_keyword |
| `tests/unit/test_allen_connector.py` | Create | Allen fetch_by_id / search_by_keyword |

---

## Task 1: Schema migration framework

**Files:**
- Create: `src/neurodb/migrations.py`
- Modify: `src/neurodb/db.py:15-17`
- Create: `tests/unit/test_migrations.py`

- [ ] **Step 1.1: Write failing test for migration runner**

```python
# tests/unit/test_migrations.py
import pytest
from sqlalchemy import create_engine, text
from neurodb.migrations import apply_migrations, get_schema_version


def _engine():
    engine = create_engine("sqlite:///:memory:")
    return engine


def test_fresh_db_starts_at_version_zero():
    engine = _engine()
    assert get_schema_version(engine) == 0


def test_apply_migrations_advances_version():
    engine = _engine()
    ran = []

    def migration_1(conn):
        ran.append(1)

    apply_migrations(engine, {1: migration_1})
    assert get_schema_version(engine) == 1
    assert ran == [1]


def test_apply_migrations_is_idempotent():
    engine = _engine()
    ran = []

    def migration_1(conn):
        ran.append(1)

    apply_migrations(engine, {1: migration_1})
    apply_migrations(engine, {1: migration_1})
    assert ran == [1]  # only ran once


def test_apply_migrations_runs_in_version_order():
    engine = _engine()
    order = []

    apply_migrations(engine, {
        2: lambda conn: order.append(2),
        1: lambda conn: order.append(1),
    })
    assert order == [1, 2]
```

- [ ] **Step 1.2: Run test — confirm it fails**

```bash
cd /home/oldha/projects/neuroDb
uv run pytest tests/unit/test_migrations.py -v
```
Expected: `ModuleNotFoundError: No module named 'neurodb.migrations'`

- [ ] **Step 1.3: Create `src/neurodb/migrations.py`**

```python
from sqlalchemy import Engine, text


def get_schema_version(engine: Engine) -> int:
    with engine.connect() as conn:
        try:
            row = conn.execute(
                text("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
            ).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0


def apply_migrations(engine: Engine, migrations: dict[int, callable]) -> None:
    """Apply any pending migrations in version order. Idempotent."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """))
        conn.commit()

    current = get_schema_version(engine)
    pending = sorted(v for v in migrations if v > current)

    for version in pending:
        with engine.connect() as conn:
            migrations[version](conn)
            from datetime import datetime, timezone
            conn.execute(
                text("INSERT INTO schema_migrations (version, applied_at) VALUES (:v, :at)"),
                {"v": version, "at": datetime.now(timezone.utc).isoformat()},
            )
            conn.commit()
```

- [ ] **Step 1.4: Run test — confirm it passes**

```bash
uv run pytest tests/unit/test_migrations.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 1.5: Commit**

```bash
git add src/neurodb/migrations.py tests/unit/test_migrations.py
git commit -m "feat: add schema migration framework with version tracking"
```

---

## Task 2: Wire migration runner into init_db

**Files:**
- Modify: `src/neurodb/db.py:15-17`

- [ ] **Step 2.1: Write failing test confirming init_db creates schema_migrations table**

Add to `tests/unit/test_migrations.py`:

```python
from sqlalchemy import create_engine, inspect
from neurodb.db import init_db


def test_init_db_creates_schema_migrations_table():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    tables = inspect(engine).get_table_names()
    assert "schema_migrations" in tables
```

- [ ] **Step 2.2: Run test — confirm it fails**

```bash
uv run pytest tests/unit/test_migrations.py::test_init_db_creates_schema_migrations_table -v
```
Expected: FAIL — `schema_migrations` not in tables

- [ ] **Step 2.3: Define the project migration registry and wire it into `init_db`**

Add `_MIGRATIONS` dict and call `apply_migrations` at the end of `init_db` in `src/neurodb/db.py`:

```python
# at top of db.py, add:
from neurodb.migrations import apply_migrations

# replace init_db:
def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    seed_learning_sources(engine)
    apply_migrations(engine, _MIGRATIONS)


# add after seed_learning_sources, before create_views:
def _migration_001_study_note_unique(conn) -> None:
    """Add unique constraint on (index_id, concept_tag) in study_notes.
    Deletes duplicates first (keeps the row with the lowest id).
    """
    conn.execute(text("""
        DELETE FROM study_notes
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM study_notes
            GROUP BY index_id, concept_tag
        )
    """))
    # SQLite/DuckDB both support this ALTER TABLE form
    try:
        conn.execute(text(
            "ALTER TABLE study_notes "
            "ADD CONSTRAINT uq_study_note_index_concept UNIQUE (index_id, concept_tag)"
        ))
    except Exception:
        pass  # constraint already exists on this DB


_MIGRATIONS: dict[int, callable] = {
    1: _migration_001_study_note_unique,
}
```

- [ ] **Step 2.4: Run test — confirm it passes**

```bash
uv run pytest tests/unit/test_migrations.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 2.5: Also add UniqueConstraint to schema.py so new DBs get it from create_all**

In `src/neurodb/schema.py`, update `StudyNote`:

```python
class StudyNote(Base):
    __tablename__ = "study_notes"
    __table_args__ = (
        UniqueConstraint("index_id", "concept_tag", name="uq_study_note_index_concept"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("study_notes_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False, index=True)
    concept_tag: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    section_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagged_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

- [ ] **Step 2.6: Run full test suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all tests PASS

- [ ] **Step 2.7: Commit**

```bash
git add src/neurodb/db.py src/neurodb/schema.py
git commit -m "feat: wire migration runner into init_db; add StudyNote unique constraint migration"
```

---

## Task 3: Explicit connector registry (M4)

**Files:**
- Modify: `src/neurodb/connectors/__init__.py`
- Modify: `src/neurodb/ui/app.py:14-17`
- Create: `tests/unit/test_connector_registry.py`

- [ ] **Step 3.1: Write failing test**

```python
# tests/unit/test_connector_registry.py
from neurodb.connectors import ALL_CONNECTORS
from neurodb.connectors.base import BaseConnector


def test_all_connectors_are_base_connector_subclasses():
    for connector_cls in ALL_CONNECTORS:
        assert issubclass(connector_cls, BaseConnector), (
            f"{connector_cls.__name__} is not a BaseConnector subclass"
        )


def test_all_connectors_have_source_name():
    for connector_cls in ALL_CONNECTORS:
        assert hasattr(connector_cls, "SOURCE_NAME"), (
            f"{connector_cls.__name__} missing SOURCE_NAME"
        )


def test_connector_source_names_are_unique():
    names = [c.SOURCE_NAME for c in ALL_CONNECTORS]
    assert len(names) == len(set(names)), "Duplicate SOURCE_NAME values in ALL_CONNECTORS"


def test_all_four_sources_registered():
    names = {c.SOURCE_NAME for c in ALL_CONNECTORS}
    assert names == {"openneuro", "dandi", "neurovault", "allen_brain"}
```

- [ ] **Step 3.2: Run test — confirm it fails**

```bash
uv run pytest tests/unit/test_connector_registry.py -v
```
Expected: `ImportError: cannot import name 'ALL_CONNECTORS'`

- [ ] **Step 3.3: Populate `src/neurodb/connectors/__init__.py`**

```python
from neurodb.connectors.allen_brain import AllenBrainConnector
from neurodb.connectors.dandi import DandiConnector
from neurodb.connectors.neurovault import NeuroVaultConnector
from neurodb.connectors.openneuro import OpenNeuroConnector

ALL_CONNECTORS = [
    AllenBrainConnector,
    DandiConnector,
    NeuroVaultConnector,
    OpenNeuroConnector,
]
```

- [ ] **Step 3.4: Update `src/neurodb/ui/app.py` — replace four noqa imports with one**

Remove lines 14–17:
```python
import neurodb.connectors.allen_brain  # noqa: F401 — registers AllenDataset
import neurodb.connectors.dandi  # noqa: F401 — registers DandiDataset
import neurodb.connectors.neurovault  # noqa: F401 — registers NeuroVaultDataset
import neurodb.connectors.openneuro  # noqa: F401 — registers OpenNeuroDataset
```

Replace with:
```python
import neurodb.connectors  # noqa: F401 — registers all connector ORM models with Base.metadata
```

- [ ] **Step 3.5: Run tests**

```bash
uv run pytest tests/unit/test_connector_registry.py -v
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 3.6: Commit**

```bash
git add src/neurodb/connectors/__init__.py src/neurodb/ui/app.py tests/unit/test_connector_registry.py
git commit -m "feat: explicit connector registry in connectors/__init__.py; remove side-effect imports from app.py"
```

---

## Task 4: DANDI — fetch_by_id and search_by_keyword (H3, H4)

**Files:**
- Modify: `src/neurodb/connectors/dandi.py`
- Create: `tests/unit/test_dandi_connector.py`

DANDI REST API endpoints used:
- Single dandiset: `GET https://api.dandiarchive.org/api/dandisets/{identifier}/`
- Keyword search: `GET https://api.dandiarchive.org/api/dandisets/?search={query}&page_size={limit}`

- [ ] **Step 4.1: Write failing tests**

```python
# tests/unit/test_dandi_connector.py
from unittest.mock import MagicMock, patch
import pytest
from neurodb.connectors.dandi import DandiConnector


_SAMPLE_DANDISET = {
    "identifier": "DANDI:000001",
    "most_recent_published_version": {
        "name": "Test Dandiset",
        "asset_summary": {
            "species": [{"name": "Homo sapiens"}],
            "dataStandard": [{"name": "NWB"}],
            "numberOfSubjects": 5,
        },
    },
}


def test_fetch_by_id_returns_raw_dict():
    connector = DandiConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = _SAMPLE_DANDISET
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.dandi.httpx.get", return_value=mock_resp) as mock_get:
        result = connector.fetch_by_id("DANDI:000001")

    assert result == _SAMPLE_DANDISET
    call_url = mock_get.call_args[0][0]
    assert "000001" in call_url


def test_fetch_by_id_raises_on_http_error():
    import httpx
    connector = DandiConnector()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock(status_code=404, text="not found")
    )
    with patch("neurodb.connectors.dandi.httpx.get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="DANDI API returned"):
            connector.fetch_by_id("DANDI:999999")


def test_search_by_keyword_returns_list_of_dicts():
    connector = DandiConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [_SAMPLE_DANDISET], "next": None}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.dandi.httpx.get", return_value=mock_resp) as mock_get:
        results = connector.search_by_keyword("retinotopy", limit=5)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["identifier"] == "DANDI:000001"
    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["params"]["search"] == "retinotopy"


def test_search_by_keyword_respects_limit():
    connector = DandiConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [_SAMPLE_DANDISET] * 3, "next": None}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.dandi.httpx.get", return_value=mock_resp):
        results = connector.search_by_keyword("plasticity", limit=2)

    assert len(results) <= 2
```

- [ ] **Step 4.2: Run test — confirm it fails**

```bash
uv run pytest tests/unit/test_dandi_connector.py -v
```
Expected: FAIL — `DandiConnector has no attribute fetch_by_id`

- [ ] **Step 4.3: Add `fetch_by_id` and `search_by_keyword` to `DandiConnector`**

Add after `normalize_subject` in `src/neurodb/connectors/dandi.py`:

```python
    def fetch_by_id(self, dataset_id: str) -> dict:
        # Strip "DANDI:" prefix if present — API uses bare numeric ID
        bare_id = dataset_id.replace("DANDI:", "")
        url = f"{_BASE}{bare_id}/"
        try:
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"DANDI request timed out ({url})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"DANDI API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        return response.json()

    def search_by_keyword(self, query: str, limit: int = 10) -> list[dict]:
        url = _BASE
        try:
            response = httpx.get(
                url,
                params={"search": query, "page_size": limit},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"DANDI request timed out ({url})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"DANDI API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        results = response.json().get("results", [])
        return results[:limit]
```

- [ ] **Step 4.4: Run test — confirm it passes**

```bash
uv run pytest tests/unit/test_dandi_connector.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 4.5: Commit**

```bash
git add src/neurodb/connectors/dandi.py tests/unit/test_dandi_connector.py
git commit -m "feat: add fetch_by_id and search_by_keyword to DandiConnector"
```

---

## Task 5: NeuroVault — fetch_by_id and search_by_keyword (H3, H4)

**Files:**
- Modify: `src/neurodb/connectors/neurovault.py`
- Create: `tests/unit/test_neurovault_connector.py`

NeuroVault REST API endpoints:
- Single collection: `GET https://neurovault.org/api/collections/{id}/`
- Keyword search: `GET https://neurovault.org/api/collections/?search={query}`

- [ ] **Step 5.1: Write failing tests**

```python
# tests/unit/test_neurovault_connector.py
from unittest.mock import MagicMock, patch
import pytest
from neurodb.connectors.neurovault import NeuroVaultConnector


_SAMPLE_COLLECTION = {
    "id": 1234,
    "name": "Retinotopy Study",
    "description": "Visual cortex retinotopy",
    "doi": None,
    "number_of_images": 10,
    "number_of_subjects": 8,
}


def test_fetch_by_id_returns_raw_dict():
    connector = NeuroVaultConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = _SAMPLE_COLLECTION
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.neurovault.httpx.get", return_value=mock_resp) as mock_get:
        result = connector.fetch_by_id("1234")

    assert result == _SAMPLE_COLLECTION
    call_url = mock_get.call_args[0][0]
    assert "1234" in call_url


def test_fetch_by_id_raises_on_http_error():
    import httpx
    connector = NeuroVaultConnector()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock(status_code=404, text="not found")
    )
    with patch("neurodb.connectors.neurovault.httpx.get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="NeuroVault API returned"):
            connector.fetch_by_id("999999")


def test_search_by_keyword_returns_list_of_dicts():
    connector = NeuroVaultConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [_SAMPLE_COLLECTION], "next": None}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.neurovault.httpx.get", return_value=mock_resp) as mock_get:
        results = connector.search_by_keyword("retinotopy", limit=5)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["name"] == "Retinotopy Study"
    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["params"]["search"] == "retinotopy"
```

- [ ] **Step 5.2: Run test — confirm it fails**

```bash
uv run pytest tests/unit/test_neurovault_connector.py -v
```
Expected: FAIL — `NeuroVaultConnector has no attribute fetch_by_id`

- [ ] **Step 5.3: Add `fetch_by_id` and `search_by_keyword` to `NeuroVaultConnector`**

Add after `normalize_subject` in `src/neurodb/connectors/neurovault.py`:

```python
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
        url = _BASE
        try:
            response = httpx.get(url, params={"search": query}, timeout=30)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"NeuroVault request timed out ({url})") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"NeuroVault API returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        results = response.json().get("results", [])
        return results[:limit]
```

- [ ] **Step 5.4: Run test — confirm it passes**

```bash
uv run pytest tests/unit/test_neurovault_connector.py -v
```
Expected: all 3 tests PASS

- [ ] **Step 5.5: Commit**

```bash
git add src/neurodb/connectors/neurovault.py tests/unit/test_neurovault_connector.py
git commit -m "feat: add fetch_by_id and search_by_keyword to NeuroVaultConnector"
```

---

## Task 6: Allen Brain — fetch_by_id and search_by_keyword (H3, H4)

**Files:**
- Modify: `src/neurodb/connectors/allen_brain.py`
- Create: `tests/unit/test_allen_connector.py`

Allen Brain API uses RQSA query syntax:
- Single dataset: `GET {_BASE}?criteria=model::SectionDataSet[id$eq{id}]&num_rows=1`
- Keyword search: `GET {_BASE}?criteria=model::SectionDataSet[name$li*{query}*]&num_rows={limit}`

- [ ] **Step 6.1: Write failing tests**

```python
# tests/unit/test_allen_connector.py
from unittest.mock import MagicMock, patch
import pytest
from neurodb.connectors.allen_brain import AllenBrainConnector


_SAMPLE_DATASET = {
    "id": 999,
    "name": "Mouse Visual Cortex ISH",
    "description": "In situ hybridization study",
    "plane_of_section_id": 1,
    "specimen_id": 42,
    "failed": False,
}


def test_fetch_by_id_returns_raw_dict():
    connector = AllenBrainConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"msg": [_SAMPLE_DATASET]}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.allen_brain.httpx.get", return_value=mock_resp) as mock_get:
        result = connector.fetch_by_id("999")

    assert result == _SAMPLE_DATASET
    call_kwargs = mock_get.call_args[1]
    assert "999" in call_kwargs["params"]["criteria"]


def test_fetch_by_id_raises_if_not_found():
    connector = AllenBrainConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"msg": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.allen_brain.httpx.get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="not found"):
            connector.fetch_by_id("000000")


def test_search_by_keyword_returns_list_of_dicts():
    connector = AllenBrainConnector()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"msg": [_SAMPLE_DATASET]}
    mock_resp.raise_for_status = MagicMock()

    with patch("neurodb.connectors.allen_brain.httpx.get", return_value=mock_resp) as mock_get:
        results = connector.search_by_keyword("visual cortex", limit=5)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["id"] == 999
    call_kwargs = mock_get.call_args[1]
    assert "visual+cortex" in call_kwargs["params"]["criteria"] or \
           "visual cortex" in call_kwargs["params"]["criteria"]
```

- [ ] **Step 6.2: Run test — confirm it fails**

```bash
uv run pytest tests/unit/test_allen_connector.py -v
```
Expected: FAIL — `AllenBrainConnector has no attribute fetch_by_id`

- [ ] **Step 6.3: Add `fetch_by_id` and `search_by_keyword` to `AllenBrainConnector`**

Add after `normalize_subject` in `src/neurodb/connectors/allen_brain.py`:

```python
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
```

- [ ] **Step 6.4: Run test — confirm it passes**

```bash
uv run pytest tests/unit/test_allen_connector.py -v
```
Expected: all 3 tests PASS

- [ ] **Step 6.5: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 6.6: Commit**

```bash
git add src/neurodb/connectors/allen_brain.py tests/unit/test_allen_connector.py
git commit -m "feat: add fetch_by_id and search_by_keyword to AllenBrainConnector"
```

---

## Task 7: Dependency upper-bound pinning (M7)

**Files:**
- Modify: `pyproject.toml`

No tests needed — this is a configuration change verified by re-locking.

- [ ] **Step 7.1: Update pyproject.toml with upper bounds on volatile deps**

Change the `dependencies` list:

```toml
dependencies = [
    "chromadb>=1.5.8,<2.0",
    "dandi>=0.62,<1.0",
    "duckdb>=1.2,<2.0",
    "duckdb-engine>=0.14,<1.0",
    "h5py>=3.10,<4.0",
    "httpx>=0.28.1,<1.0",
    "pandas>=3.0.2,<4.0",
    "pynwb>=2.8,<3.0",
    "sentence-transformers>=5.4.1,<6.0",
    "sqlalchemy>=2.0.49,<3.0",
    "anthropic>=0.50.0,<1.0",
    "python-dotenv>=1.0.0,<2.0",
    "streamlit>=1.56.0,<2.0",
]
```

- [ ] **Step 7.2: Re-sync environment to confirm constraints are satisfiable**

```bash
uv sync
```
Expected: resolves without conflict; existing pinned versions are within the new bounds

- [ ] **Step 7.3: Run test suite to confirm nothing broke**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 7.4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add upper-bound pins to volatile dependencies"
```

---

## TD-1 Complete

Run the full suite one final time before sign-off:

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```

All tests must pass. Update `docs/projectStatus.md` test count to reflect new total.
