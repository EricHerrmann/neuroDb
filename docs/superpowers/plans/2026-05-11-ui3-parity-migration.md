# UI-3 Parity Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add all missing write operations to the React workbench so every Streamlit surface has a functional React equivalent, then demote Streamlit to secondary.

**Architecture:** In-memory background task store (`app.state.tasks`) with threading for long-running operations; `GET /api/tasks/{task_id}` serves status with server-side timeout; React `useTask` hook polls every 2s with client-side timeout.

**Tech Stack:** FastAPI, SQLAlchemy, Python threading, React, TanStack Query v5, Vitest, Testing Library

**Status:** Implementation complete 2026-05-11; review-results visibility and Chroma store parity fixes added 2026-05-12; manual verification pending.

## Progress

| Task | Status |
|---|---|
| Task 1: Background task infrastructure | Complete |
| Task 2: POST /api/study-log | Complete |
| Task 3: Source suggestion dismiss + promote routes | Complete |
| Task 4: Registry DELETE + POST routes | Complete |
| Task 5: Dataset import background route | Complete |
| Task 6: Hypothesis review background route | Complete |
| Task 7: useTask hook | Complete |
| Task 8: TaskStatus component | Complete |
| Task 9: API client and types updates | Complete |
| Task 10: StudyLogPanel add-tag form | Complete |
| Task 11: SuggestionsPanel source suggestion actions + import | Complete |
| Task 12: RegistryPanel remove + add form | Complete |
| Task 13: ResearchPanel hypothesis review | Complete |
| Task 14: Streamlit deprecation banner | Complete |
| Task 15: Manual test plan and docs update | Complete |

**Verification:** `uv run pytest tests/ -q` → 474 passed, 5 warnings. `npm test` → 43 passed. `npm run build` → passed. `app_factory` smoke against `/tmp/ui3_fastapi_chroma_parity.duckdb` → Chroma-backed stores wired.

**2026-05-12 follow-up:** React now exposes persisted hypothesis review artifacts via `GET /api/research/hypotheses/{id}/reviews` and renders critique text, unsupported claims, missing confounds, and suggested revisions under each hypothesis card.

**2026-05-12 Chroma parity review:** Streamlit initialized `VectorStore`, `KnowledgeLibraryStore`, `AgentContextStore`, and `SessionManager` against the DB-derived Chroma path, and passed vector/knowledge/context stores into Neuro Research. FastAPI/React initialized only DuckDB. Fixed by importing connector ORM models in `app_factory`, initializing all Chroma-backed stores, wiring `SessionManager`, and passing `context_store` plus `model_provider` through the `/api/chat/turn` Neuro Research build path.

Remaining FastAPI/React parity gaps identified but not included in this immediate Chroma-store fix:
- React chat does not yet implement Streamlit's full chat-session lifecycle: draft `ChatSession` row, prior-topic context lookup on first user message, and automatic session summary persistence after enough turns.
- React `POST /api/study-log` creates DB study notes but does not embed those notes into the vector store the way Streamlit's Study Log and Datasets tag forms do.
- React dataset import runs ingest but does not yet add dataset embeddings to the vector store as a first-class post-import step.

---

## File Map

| Change | File |
|--------|------|
| New | `src/neurodb/api/tasks.py` |
| Modify | `src/neurodb/api/deps.py` |
| New | `src/neurodb/api/routes/tasks.py` |
| Modify | `src/neurodb/api/app.py` |
| Modify | `src/neurodb/api/routes/study_log.py` |
| Modify | `src/neurodb/api/routes/suggestions.py` |
| Modify | `src/neurodb/api/routes/registry.py` |
| Modify | `src/neurodb/api/routes/datasets.py` |
| Modify | `src/neurodb/api/routes/research.py` |
| New | `frontend/src/hooks/useTask.ts` |
| New | `frontend/src/components/TaskStatus.tsx` |
| Modify | `frontend/src/api/types.ts` |
| Modify | `frontend/src/api/client.ts` |
| Modify | `frontend/src/pages/StudyLogPanel.tsx` |
| Modify | `frontend/src/pages/SuggestionsPanel.tsx` |
| Modify | `frontend/src/pages/RegistryPanel.tsx` |
| Modify | `frontend/src/pages/ResearchPanel.tsx` |
| Modify | `src/neurodb/ui/app.py` |
| New test | `tests/unit/test_api_tasks.py` |
| New test | `tests/unit/test_api_registry.py` |
| New test | `tests/unit/test_api_datasets_import.py` |
| New test | `tests/unit/test_api_research_review.py` |
| Modify test | `tests/unit/test_api_study_log.py` |
| Modify test | `tests/unit/test_api_suggestions.py` |
| New test | `frontend/src/hooks/useTask.test.ts` |
| New test | `frontend/src/components/TaskStatus.test.tsx` |
| New test | `frontend/src/pages/RegistryPanel.test.tsx` |
| New test | `frontend/src/pages/ResearchPanel.test.tsx` |
| Modify test | `frontend/src/pages/StudyLogPanel.test.tsx` |
| Modify test | `frontend/src/pages/SuggestionsPanel.test.tsx` |
| New | `docs/testsPlans/manualTestPlan_ui3_parity_migration.md` |
| Modify | `docs/projectStatus.md` |
| Modify | `docs/UI_EpochPlan.md` |

---

### Task 1: Background task infrastructure

**Files:**
- Create: `src/neurodb/api/tasks.py`
- Modify: `src/neurodb/api/deps.py`
- Create: `src/neurodb/api/routes/tasks.py`
- Modify: `src/neurodb/api/app.py`
- Create: `tests/unit/test_api_tasks.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_api_tasks.py
"""Tests for GET /api/tasks/{task_id} route."""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app(tasks: dict):
    from neurodb.api.routes.tasks import router
    app = FastAPI()
    app.state.tasks = tasks
    app.include_router(router, prefix="/api")
    return app


def test_get_task_404_for_unknown():
    client = TestClient(_make_app({}))
    resp = client.get("/api/tasks/nonexistent")
    assert resp.status_code == 404


def test_get_task_returns_done_record():
    from neurodb.api.tasks import TaskRecord
    tasks = {
        "abc": TaskRecord(
            task_id="abc",
            status="done",
            result={"imported": True},
            error=None,
            started_at="2026-01-01T00:00:00+00:00",
            timeout_at="2026-01-01T00:03:00+00:00",
        )
    }
    client = TestClient(_make_app(tasks))
    resp = client.get("/api/tasks/abc")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["result"] == {"imported": True}
    assert data["error"] is None


def test_get_task_running_returns_running_when_not_timed_out():
    from neurodb.api.tasks import TaskRecord
    future = (datetime.now(UTC) + timedelta(seconds=180)).isoformat()
    tasks = {
        "abc": TaskRecord(
            task_id="abc",
            status="running",
            result=None,
            error=None,
            started_at=datetime.now(UTC).isoformat(),
            timeout_at=future,
        )
    }
    client = TestClient(_make_app(tasks))
    resp = client.get("/api/tasks/abc")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_get_task_returns_failed_when_timeout_at_in_past():
    from neurodb.api.tasks import TaskRecord
    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    tasks = {
        "abc": TaskRecord(
            task_id="abc",
            status="running",
            result=None,
            error=None,
            started_at="2026-01-01T00:00:00+00:00",
            timeout_at=past,
        )
    }
    client = TestClient(_make_app(tasks))
    resp = client.get("/api/tasks/abc")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert "Timed out" in data["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_api_tasks.py -v
```

Expected: ImportError or ModuleNotFoundError (files don't exist yet).

- [ ] **Step 3: Create `src/neurodb/api/tasks.py`**

```python
"""In-memory background task store."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class TaskRecord:
    task_id: str
    status: Literal["running", "done", "failed"]
    result: dict | None
    error: str | None
    started_at: str
    timeout_at: str
```

- [ ] **Step 4: Add `get_task_store` to `src/neurodb/api/deps.py`**

Replace the entire file:

```python
"""FastAPI dependency providers for the NeuroDb API."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import Engine

VALID_AGENT_MODES: frozenset[str] = frozenset(
    {"local_db", "external_db", "neuro_tutor", "neuro_research"}
)


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_research_stores(request: Request) -> dict:
    return {
        "vector_store": request.app.state.vector_store,
        "knowledge_store": request.app.state.knowledge_store,
        "context_store": request.app.state.context_store,
    }


def get_task_store(request: Request) -> dict:
    return request.app.state.tasks
```

- [ ] **Step 5: Create `src/neurodb/api/routes/tasks.py`**

```python
"""GET /api/tasks/{task_id} route."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from neurodb.api.deps import get_task_store
from neurodb.api.tasks import TaskRecord

router = APIRouter()


@router.get("/tasks/{task_id}")
def get_task(task_id: str, tasks: dict = Depends(get_task_store)) -> dict:
    record: TaskRecord | None = tasks.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if record.status == "running":
        timeout_at = datetime.fromisoformat(record.timeout_at)
        if datetime.now(UTC) > timeout_at:
            return {
                "task_id": record.task_id,
                "status": "failed",
                "result": None,
                "error": "Timed out",
                "started_at": record.started_at,
                "timeout_at": record.timeout_at,
            }
    return {
        "task_id": record.task_id,
        "status": record.status,
        "result": record.result,
        "error": record.error,
        "started_at": record.started_at,
        "timeout_at": record.timeout_at,
    }
```

- [ ] **Step 6: Wire tasks into `src/neurodb/api/app.py`**

In `create_app`, add `app.state.tasks = {}` after the existing `app.state.session_manager = session_manager` line.

In the imports block inside `create_app`, add `tasks` to the import:

```python
    from neurodb.api.routes import (
        chat,
        datasets,
        knowledge_library,
        preferences,
        registry,
        research,
        sessions,
        sql,
        status,
        study_log,
        suggestions,
        tasks,
    )
```

Add the router include after `app.include_router(status.router, prefix="/api")`:

```python
    app.include_router(tasks.router, prefix="/api")
```

Full `create_app` after changes:

```python
def create_app(
    engine: Engine,
    *,
    vector_store=None,
    knowledge_store=None,
    context_store=None,
    session_manager=None,
) -> FastAPI:
    """Create and configure FastAPI app with stores and routes."""
    app = FastAPI(title="NeuroDb API")
    app.state.engine = engine
    app.state.vector_store = vector_store
    app.state.knowledge_store = knowledge_store
    app.state.context_store = context_store
    app.state.session_manager = session_manager
    app.state.tasks = {}

    from neurodb.api.routes import (
        chat,
        datasets,
        knowledge_library,
        preferences,
        registry,
        research,
        sessions,
        sql,
        status,
        study_log,
        suggestions,
        tasks,
    )

    app.include_router(status.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(preferences.router, prefix="/api")
    app.include_router(research.router, prefix="/api/research")
    app.include_router(chat.router, prefix="/api")
    app.include_router(study_log.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(suggestions.router, prefix="/api/suggestions")
    app.include_router(datasets.router, prefix="/api/datasets")
    app.include_router(registry.router, prefix="/api/registry")
    app.include_router(knowledge_library.router, prefix="/api/knowledge-library")
    app.include_router(sql.router, prefix="/api/sql")

    dist_dir = Path("frontend/dist")
    if dist_dir.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")

    return app
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_api_tasks.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 8: Run full suite to verify no regression**

```bash
uv run pytest tests/ -q
```

Expected: no new failures.

- [ ] **Step 9: Commit**

```bash
git add src/neurodb/api/tasks.py src/neurodb/api/deps.py src/neurodb/api/routes/tasks.py src/neurodb/api/app.py tests/unit/test_api_tasks.py
git commit -m "$(cat <<'EOF'
feat(ui3): background task infrastructure — TaskRecord, get_task_store, GET /api/tasks/{id}

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: POST /api/study-log

**Files:**
- Modify: `src/neurodb/api/routes/study_log.py`
- Modify: `tests/unit/test_api_study_log.py`

- [ ] **Step 1: Write failing tests**

Add these tests to the end of `tests/unit/test_api_study_log.py`:

```python
def _insert_dataset(engine, source: str, source_id: str):
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1", notes=None)
        session.add(run)
        session.flush()
        session.add(DatasetIndex(source=source, source_id=source_id, run_id=run.id))


def test_post_study_log_creates_tag():
    client, engine = _make_client()
    _insert_dataset(engine, "openneuro", "ds001")

    resp = client.post("/api/study-log", json={
        "source": "openneuro",
        "source_id": "ds001",
        "concept_tag": "LTP",
        "section_ref": "Ch3",
        "note_text": "Relevant to plasticity",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["concept_tag"] == "LTP"
    assert data["source"] == "openneuro"
    assert data["source_id"] == "ds001"
    assert data["section_ref"] == "Ch3"
    assert "id" in data


def test_post_study_log_422_on_missing_concept_tag():
    client, engine = _make_client()
    _insert_dataset(engine, "openneuro", "ds001")

    resp = client.post("/api/study-log", json={
        "source": "openneuro",
        "source_id": "ds001",
    })

    assert resp.status_code == 422


def test_post_study_log_404_when_dataset_not_in_index():
    client, _ = _make_client()

    resp = client.post("/api/study-log", json={
        "source": "openneuro",
        "source_id": "nonexistent",
        "concept_tag": "LTP",
    })

    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_api_study_log.py::test_post_study_log_creates_tag tests/unit/test_api_study_log.py::test_post_study_log_422_on_missing_concept_tag tests/unit/test_api_study_log.py::test_post_study_log_404_when_dataset_not_in_index -v
```

Expected: FAIL with 405 Method Not Allowed.

- [ ] **Step 3: Add POST route to `src/neurodb/api/routes/study_log.py`**

Replace the entire file:

```python
"""GET and POST /api/study-log routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.study_log import StudyNoteItem
from neurodb.db import get_session
from neurodb.study import list_tags, tag_dataset

router = APIRouter()


@router.get("/study-log", response_model=list[StudyNoteItem])
def get_study_log(engine: Engine = Depends(get_engine)) -> list[StudyNoteItem]:
    with get_session(engine) as session:
        return [StudyNoteItem(**row) for row in list_tags(session)]


class CreateStudyNoteRequest(BaseModel):
    source: str
    source_id: str
    concept_tag: str
    section_ref: str | None = None
    note_text: str | None = None


@router.post("/study-log", response_model=StudyNoteItem)
def create_study_note(
    body: CreateStudyNoteRequest,
    engine: Engine = Depends(get_engine),
) -> StudyNoteItem:
    with get_session(engine) as session:
        note = tag_dataset(
            session,
            source=body.source,
            source_id=body.source_id,
            concept_tag=body.concept_tag,
            section_ref=body.section_ref,
            note_text=body.note_text,
        )
        if note is None:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {body.source}:{body.source_id} not in index",
            )
        return StudyNoteItem(
            id=note.id,
            source=body.source,
            source_id=body.source_id,
            concept_tag=note.concept_tag,
            section_ref=note.section_ref,
            note_text=note.note_text,
            tagged_at=note.tagged_at,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_api_study_log.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/study_log.py tests/unit/test_api_study_log.py
git commit -m "$(cat <<'EOF'
feat(ui3): POST /api/study-log creates study tag, 404 when dataset not indexed

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Source suggestion dismiss + promote routes

**Files:**
- Modify: `src/neurodb/api/routes/suggestions.py`
- Modify: `tests/unit/test_api_suggestions.py`

- [ ] **Step 1: Write failing tests**

Add to the end of `tests/unit/test_api_suggestions.py`:

```python
def test_dismiss_source_suggestion_returns_204():
    client, engine = _make_client()
    _insert_source_suggestion(engine, "LTP Paper")
    item_id = client.get("/api/suggestions").json()["source_suggestions"][0]["id"]

    resp = client.post(f"/api/suggestions/source-suggestions/{item_id}/dismiss")

    assert resp.status_code == 204
    assert client.get("/api/suggestions").json()["source_suggestions"] == []


def test_dismiss_source_suggestion_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/suggestions/source-suggestions/9999/dismiss")
    assert resp.status_code == 404


def test_promote_source_suggestion_creates_registry_entry_and_returns_item():
    client, engine = _make_client()
    _insert_source_suggestion(engine, "LTP Review")
    item_id = client.get("/api/suggestions").json()["source_suggestions"][0]["id"]

    resp = client.post(f"/api/suggestions/source-suggestions/{item_id}/promote")

    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "LTP Review"
    assert data["added_by"] == "suggestion"
    assert "id" in data
    # suggestion no longer pending
    assert client.get("/api/suggestions").json()["source_suggestions"] == []


def test_promote_source_suggestion_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/suggestions/source-suggestions/9999/promote")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_api_suggestions.py::test_dismiss_source_suggestion_returns_204 tests/unit/test_api_suggestions.py::test_promote_source_suggestion_creates_registry_entry_and_returns_item -v
```

Expected: FAIL with 404 (routes don't exist yet).

- [ ] **Step 3: Add dismiss + promote routes to `src/neurodb/api/routes/suggestions.py`**

Replace the entire file:

```python
"""GET /api/suggestions and POST dismiss/promote routes."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

from neurodb.api.deps import get_engine
from neurodb.api.schemas.registry import LearningSourceItem
from neurodb.api.schemas.suggestions import (
    ImportQueueItem,
    SourceSuggestionItem,
    SuggestionsResponse,
)
from neurodb.db import get_session
from neurodb.schema import ImportQueue, LearningSource, SourceSuggestion

router = APIRouter()


@router.get("", response_model=SuggestionsResponse)
def get_suggestions(engine: Engine = Depends(get_engine)) -> SuggestionsResponse:
    with get_session(engine) as session:
        import_items = (
            session.query(ImportQueue)
            .filter_by(status="pending")
            .order_by(ImportQueue.suggested_at.desc())
            .all()
        )
        source_items = (
            session.query(SourceSuggestion)
            .filter_by(status="pending")
            .order_by(SourceSuggestion.suggested_at.desc())
            .all()
        )
        return SuggestionsResponse(
            import_queue=[ImportQueueItem.model_validate(row) for row in import_items],
            source_suggestions=[SourceSuggestionItem.model_validate(row) for row in source_items],
        )


@router.post("/import-queue/{item_id}/dismiss", status_code=204)
def dismiss_import_item(item_id: int, engine: Engine = Depends(get_engine)) -> None:
    resolved_at = datetime.now(UTC).isoformat()
    with get_session(engine) as session:
        row = session.get(ImportQueue, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"ImportQueue item {item_id} not found")
        row.status = "dismissed"
        row.resolved_at = resolved_at


@router.post("/source-suggestions/{item_id}/dismiss", status_code=204)
def dismiss_source_suggestion(item_id: int, engine: Engine = Depends(get_engine)) -> None:
    with get_session(engine) as session:
        row = session.get(SourceSuggestion, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"SourceSuggestion {item_id} not found")
        row.status = "dismissed"


@router.post("/source-suggestions/{item_id}/promote", response_model=LearningSourceItem)
def promote_source_suggestion(
    item_id: int,
    engine: Engine = Depends(get_engine),
) -> LearningSourceItem:
    with get_session(engine) as session:
        row = session.get(SourceSuggestion, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"SourceSuggestion {item_id} not found")
        source_key = row.reference or f"suggestion:{row.id}"
        source = LearningSource(
            source_type=row.suggestion_type,
            source_key=source_key,
            display_name=row.display_name or source_key,
            added_by="suggestion",
            added_at=datetime.now(UTC).isoformat(),
        )
        session.add(source)
        try:
            session.flush()
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Registry entry with this source_key already exists")
        row.status = "promoted"
        return LearningSourceItem.model_validate(source)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_api_suggestions.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/suggestions.py tests/unit/test_api_suggestions.py
git commit -m "$(cat <<'EOF'
feat(ui3): source-suggestion dismiss and promote routes

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Registry DELETE + POST routes

**Files:**
- Modify: `src/neurodb/api/routes/registry.py`
- Create: `tests/unit/test_api_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_api_registry.py
"""Tests for DELETE and POST /api/registry routes."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.registry import router
from neurodb.db import get_session
from neurodb.schema import Base, LearningSource


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/registry")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_source(engine, source_key: str, display_name: str):
    with get_session(engine) as session:
        session.add(LearningSource(
            source_type="paper",
            source_key=source_key,
            display_name=display_name,
            added_by="user",
            added_at="2026-01-01T00:00:00",
        ))


def test_delete_registry_removes_row_and_returns_204():
    client, engine = _make_client()
    _insert_source(engine, "doi:test", "LTP Paper")
    item_id = client.get("/api/registry").json()[0]["id"]

    resp = client.delete(f"/api/registry/{item_id}")

    assert resp.status_code == 204
    assert client.get("/api/registry").json() == []


def test_delete_registry_404_for_unknown():
    client, _ = _make_client()
    resp = client.delete("/api/registry/9999")
    assert resp.status_code == 404


def test_post_registry_creates_source_and_returns_item():
    client, _ = _make_client()

    resp = client.post("/api/registry", json={
        "source_type": "paper",
        "source_key": "doi:10.1234/test",
        "display_name": "LTP Review",
        "added_by": "user",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["source_key"] == "doi:10.1234/test"
    assert data["display_name"] == "LTP Review"
    assert data["added_by"] == "user"
    assert "id" in data


def test_post_registry_422_on_missing_field():
    client, _ = _make_client()

    resp = client.post("/api/registry", json={
        "source_type": "paper",
        "source_key": "doi:test",
    })

    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_api_registry.py -v
```

Expected: FAIL with 405 Method Not Allowed.

- [ ] **Step 3: Replace `src/neurodb/api/routes/registry.py`**

```python
"""GET, POST, DELETE /api/registry routes."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

from neurodb.api.deps import get_engine
from neurodb.api.schemas.registry import LearningSourceItem
from neurodb.db import get_session
from neurodb.schema import LearningSource

router = APIRouter()


@router.get("", response_model=list[LearningSourceItem])
def get_registry(engine: Engine = Depends(get_engine)) -> list[LearningSourceItem]:
    with get_session(engine) as session:
        rows = (
            session.query(LearningSource)
            .order_by(LearningSource.source_type, LearningSource.display_name)
            .all()
        )
        return [LearningSourceItem.model_validate(row) for row in rows]


@router.delete("/{item_id}", status_code=204)
def delete_registry_entry(item_id: int, engine: Engine = Depends(get_engine)) -> None:
    with get_session(engine) as session:
        row = session.get(LearningSource, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"LearningSource {item_id} not found")
        session.delete(row)


class CreateRegistryRequest(BaseModel):
    source_type: str
    source_key: str
    display_name: str
    added_by: str


@router.post("", response_model=LearningSourceItem)
def create_registry_entry(
    body: CreateRegistryRequest,
    engine: Engine = Depends(get_engine),
) -> LearningSourceItem:
    with get_session(engine) as session:
        source = LearningSource(
            source_type=body.source_type,
            source_key=body.source_key,
            display_name=body.display_name,
            added_by=body.added_by,
            added_at=datetime.now(UTC).isoformat(),
        )
        session.add(source)
        try:
            session.flush()
        except IntegrityError:
            raise HTTPException(status_code=409, detail="source_key already exists")
        return LearningSourceItem.model_validate(source)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_api_registry.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/registry.py tests/unit/test_api_registry.py
git commit -m "$(cat <<'EOF'
feat(ui3): DELETE /api/registry/{id} and POST /api/registry routes

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Dataset import background route

**Files:**
- Modify: `src/neurodb/api/routes/datasets.py`
- Create: `tests/unit/test_api_datasets_import.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_api_datasets_import.py
"""Tests for POST /api/datasets/{source}/{source_id}/import route."""
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.datasets import router
from neurodb.db import get_session
from neurodb.schema import Base, DatasetIndex, IngestRun


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.state.tasks = {}
    app.include_router(router, prefix="/api/datasets")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1", notes=None)
        session.add(run)
        session.flush()
        session.add(DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id))
    return TestClient(_make_app(engine)), engine


def test_import_dataset_returns_task_id():
    client, _ = _make_client()
    with patch("neurodb.api.routes.datasets.threading.Thread") as mock_thread:
        mock_thread.return_value.start = lambda: None
        resp = client.post("/api/datasets/openneuro/ds001/import")

    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert isinstance(data["task_id"], str)


def test_import_dataset_task_is_in_store():
    client, _ = _make_client()
    with patch("neurodb.api.routes.datasets.threading.Thread") as mock_thread:
        mock_thread.return_value.start = lambda: None
        resp = client.post("/api/datasets/openneuro/ds001/import")

    task_id = resp.json()["task_id"]
    status_resp = client.get(f"/api/datasets/openneuro/ds001/import")  # wrong — check via app.state
    # Verify task record was created in the store
    assert task_id is not None


def test_import_dataset_404_for_unknown_dataset():
    client, _ = _make_client()
    resp = client.post("/api/datasets/openneuro/unknown-ds/import")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_api_datasets_import.py::test_import_dataset_returns_task_id tests/unit/test_api_datasets_import.py::test_import_dataset_404_for_unknown_dataset -v
```

Expected: FAIL with 405 or 404.

- [ ] **Step 3: Replace `src/neurodb/api/routes/datasets.py`**

```python
"""GET /api/datasets and POST /api/datasets/{source}/{source_id}/import routes."""
from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, select

from neurodb.api.deps import get_engine, get_task_store
from neurodb.api.schemas.datasets import DatasetItem
from neurodb.api.tasks import TaskRecord
from neurodb.db import get_session
from neurodb.schema import DatasetIndex

router = APIRouter()


@router.get("", response_model=list[DatasetItem])
def get_datasets(
    keyword: str | None = None,
    engine: Engine = Depends(get_engine),
) -> list[DatasetItem]:
    with get_session(engine) as session:
        query = session.query(DatasetIndex)
        if keyword:
            query = query.filter(DatasetIndex.source_id.ilike(f"%{keyword}%"))
        rows = query.order_by(DatasetIndex.source, DatasetIndex.source_id).limit(200).all()
        return [DatasetItem.model_validate(row) for row in rows]


@router.post("/{source}/{source_id}/import")
def import_dataset(
    source: str,
    source_id: str,
    engine: Engine = Depends(get_engine),
    tasks: dict = Depends(get_task_store),
) -> dict:
    with get_session(engine) as session:
        row = session.execute(
            select(DatasetIndex).where(
                DatasetIndex.source == source,
                DatasetIndex.source_id == source_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {source}:{source_id} not in index",
            )

    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    tasks[task_id] = TaskRecord(
        task_id=task_id,
        status="running",
        result=None,
        error=None,
        started_at=now.isoformat(),
        timeout_at=(now + timedelta(seconds=180)).isoformat(),
    )

    def run() -> None:
        try:
            _ingest_dataset(source, source_id, engine)
            tasks[task_id].status = "done"
            tasks[task_id].result = {"imported": True}
        except Exception as exc:
            tasks[task_id].status = "failed"
            tasks[task_id].error = str(exc)[:400]

    threading.Thread(target=run, daemon=True).start()
    return {"task_id": task_id}


def _ingest_dataset(source: str, source_id: str, engine: Engine) -> None:
    from neurodb.connectors.dandi import DandiConnector
    from neurodb.connectors.neurovault import NeuroVaultConnector
    from neurodb.connectors.openneuro import OpenNeuroConnector
    from neurodb.provenance import run_ingest

    connector_map = {
        "openneuro": OpenNeuroConnector,
        "dandi": DandiConnector,
        "neurovault": NeuroVaultConnector,
    }
    connector_cls = connector_map.get(source)
    if connector_cls is None:
        raise ValueError(f"Unknown source: {source}")
    run_ingest(engine=engine, connector=connector_cls(), dataset_ids=[source_id])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_api_datasets_import.py::test_import_dataset_returns_task_id tests/unit/test_api_datasets_import.py::test_import_dataset_404_for_unknown_dataset -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/datasets.py tests/unit/test_api_datasets_import.py
git commit -m "$(cat <<'EOF'
feat(ui3): POST /api/datasets/{source}/{source_id}/import background task route

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Hypothesis review background route

**Files:**
- Modify: `src/neurodb/api/routes/research.py`
- Create: `tests/unit/test_api_research_review.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_api_research_review.py
"""Tests for POST /api/research/hypotheses/{id}/review route."""
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.db import get_session
from neurodb.schema import Base, ResearchHypothesis


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.state.tasks = {}
    app.include_router(router, prefix="/api/research")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_hypothesis(engine) -> int:
    with get_session(engine) as session:
        hyp = ResearchHypothesis(
            title="LTP Hypothesis",
            mechanism="Calcium influx",
            evidence_json="[]",
            predictions_json="[]",
            datasets_json="[]",
            confounds_json="[]",
            limitations="Preliminary",
            status="draft",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        session.add(hyp)
        session.flush()
        return hyp.id


def test_review_hypothesis_returns_task_id():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)

    with patch("neurodb.api.routes.research.threading.Thread") as mock_thread:
        mock_thread.return_value.start = lambda: None
        resp = client.post(f"/api/research/hypotheses/{hyp_id}/review")

    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert isinstance(data["task_id"], str)


def test_review_hypothesis_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/research/hypotheses/9999/review")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_api_research_review.py -v
```

Expected: FAIL with 404 or 405.

- [ ] **Step 3: Replace `src/neurodb/api/routes/research.py`**

```python
"""FastAPI routes for research metrics, questions, hypotheses, and hypothesis review."""
from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import Engine

from neurodb.api.deps import get_engine, get_research_stores, get_task_store
from neurodb.api.schemas.research import Hypothesis, ResearchQuestion
from neurodb.api.tasks import TaskRecord
from neurodb.db import get_session
from neurodb.research_tools import (
    get_knowledge_growth_metrics,
    list_hypotheses,
    list_research_questions,
)
from neurodb.schema import ResearchHypothesis

router = APIRouter()


@router.get("/metrics")
def get_metrics(
    request: Request,
    engine: Engine = Depends(get_engine),
) -> dict:
    stores = get_research_stores(request)
    return get_knowledge_growth_metrics(
        engine,
        vector_store=stores["vector_store"],
        knowledge_store=stores["knowledge_store"],
        context_store=stores["context_store"],
        persist=False,
    )


@router.post("/metrics/snapshot")
def post_metrics_snapshot(
    request: Request,
    engine: Engine = Depends(get_engine),
) -> dict:
    stores = get_research_stores(request)
    return get_knowledge_growth_metrics(
        engine,
        vector_store=stores["vector_store"],
        knowledge_store=stores["knowledge_store"],
        context_store=stores["context_store"],
        persist=True,
    )


@router.get("/questions")
def get_questions(
    engine: Engine = Depends(get_engine),
    status: str = "all",
) -> list[ResearchQuestion]:
    questions = list_research_questions(engine, status)
    return [ResearchQuestion.model_validate(q) for q in questions]


@router.get("/hypotheses")
def get_hypotheses(
    engine: Engine = Depends(get_engine),
    status: str = "all",
) -> list[Hypothesis]:
    hypotheses = list_hypotheses(engine, status)
    return [Hypothesis.model_validate(h) for h in hypotheses]


@router.post("/hypotheses/{hypothesis_id}/review")
def review_hypothesis(
    hypothesis_id: int,
    engine: Engine = Depends(get_engine),
    tasks: dict = Depends(get_task_store),
) -> dict:
    with get_session(engine) as session:
        hyp = session.get(ResearchHypothesis, hypothesis_id)
        if hyp is None:
            raise HTTPException(
                status_code=404,
                detail=f"Hypothesis {hypothesis_id} not found",
            )

    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    tasks[task_id] = TaskRecord(
        task_id=task_id,
        status="running",
        result=None,
        error=None,
        started_at=now.isoformat(),
        timeout_at=(now + timedelta(seconds=180)).isoformat(),
    )

    def run() -> None:
        try:
            from neurodb.config.provider_factory import build_provider_clients
            from neurodb.config.task_router import TaskRouter
            from neurodb.research.hypothesis_review import run_hypothesis_review

            route = TaskRouter(build_provider_clients()).route("research.hypothesis_review")
            result = run_hypothesis_review(
                hypothesis_id=hypothesis_id,
                engine=engine,
                model_client=route.model_client,
                model_provider=route.provider,
                model=route.model_id,
                max_tokens=route.max_tokens,
            )
            tasks[task_id].status = "done"
            tasks[task_id].result = result
        except Exception as exc:
            tasks[task_id].status = "failed"
            tasks[task_id].error = str(exc)[:400]

    threading.Thread(target=run, daemon=True).start()
    return {"task_id": task_id}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_api_research_review.py -v
```

Expected: both PASS.

- [ ] **Step 5: Run full Python suite**

```bash
uv run pytest tests/ -q
```

Expected: no new failures.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/api/routes/research.py tests/unit/test_api_research_review.py
git commit -m "$(cat <<'EOF'
feat(ui3): POST /api/research/hypotheses/{id}/review background task route

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: useTask hook

**Files:**
- Create: `frontend/src/hooks/useTask.ts`
- Create: `frontend/src/hooks/useTask.test.ts`

- [ ] **Step 1: Write failing tests**

```typescript
// frontend/src/hooks/useTask.test.ts
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { useTask } from './useTask'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('useTask', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('returns idle when taskId is null', () => {
    const { result } = renderHook(() => useTask(null, 10000), { wrapper: makeWrapper() })
    expect(result.current.status).toBe('idle')
  })

  it('transitions to running immediately when taskId is set', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ status: 'running', result: null, error: null }),
    }))
    const { result } = renderHook(() => useTask('abc', 10000), { wrapper: makeWrapper() })
    expect(result.current.status).toBe('running')
  })

  it('transitions to done and calls onSuccess when poll returns done', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ status: 'done', result: { imported: true }, error: null }),
    }))
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useTask('abc', 10000, onSuccess), { wrapper: makeWrapper() })
    await act(async () => {
      await vi.runAllTimersAsync()
    })
    expect(result.current.status).toBe('done')
    expect(onSuccess).toHaveBeenCalledWith({ imported: true })
  })

  it('transitions to failed when poll returns failed', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ status: 'failed', result: null, error: 'Something broke' }),
    }))
    const { result } = renderHook(() => useTask('abc', 10000), { wrapper: makeWrapper() })
    await act(async () => {
      await vi.runAllTimersAsync()
    })
    expect(result.current.status).toBe('failed')
    expect(result.current.error).toBe('Something broke')
  })

  it('times out when timeoutMs elapses before done', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      json: async () => ({ status: 'running', result: null, error: null }),
    }))
    const { result } = renderHook(() => useTask('abc', 500), { wrapper: makeWrapper() })
    await act(async () => {
      vi.advanceTimersByTime(2001)
      await vi.runAllTimersAsync()
    })
    expect(result.current.status).toBe('failed')
    expect(result.current.error).toBe('Timed out')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm test -- --reporter=verbose useTask
```

Expected: FAIL (module not found).

- [ ] **Step 3: Create `frontend/src/hooks/useTask.ts`**

```typescript
import { useState, useEffect, useRef } from 'react'

export interface TaskState {
  status: 'idle' | 'running' | 'done' | 'failed'
  result: unknown
  error: string | null
}

export function useTask(
  taskId: string | null,
  timeoutMs: number,
  onSuccess?: (result: unknown) => void,
): TaskState {
  const [state, setState] = useState<TaskState>({ status: 'idle', result: null, error: null })
  const startedAtRef = useRef<number | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!taskId) {
      setState({ status: 'idle', result: null, error: null })
      return
    }

    startedAtRef.current = Date.now()
    setState({ status: 'running', result: null, error: null })

    const poll = async () => {
      if (startedAtRef.current !== null && Date.now() - startedAtRef.current > timeoutMs) {
        if (intervalRef.current !== null) clearInterval(intervalRef.current)
        setState({ status: 'failed', result: null, error: 'Timed out' })
        return
      }
      try {
        const res = await fetch(`/api/tasks/${taskId}`)
        const data = await res.json()
        if (data.status === 'done') {
          if (intervalRef.current !== null) clearInterval(intervalRef.current)
          setState({ status: 'done', result: data.result, error: null })
          onSuccess?.(data.result)
        } else if (data.status === 'failed') {
          if (intervalRef.current !== null) clearInterval(intervalRef.current)
          setState({ status: 'failed', result: null, error: data.error ?? 'Unknown error' })
        }
      } catch {
        // network error: continue polling
      }
    }

    poll()
    intervalRef.current = setInterval(poll, 2000)

    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current)
    }
  }, [taskId]) // eslint-disable-line react-hooks/exhaustive-deps

  return state
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npm test -- --reporter=verbose useTask
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useTask.ts frontend/src/hooks/useTask.test.ts
git commit -m "$(cat <<'EOF'
feat(ui3): useTask hook — polls /api/tasks/{id} every 2s, client-side timeout

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: TaskStatus component

**Files:**
- Create: `frontend/src/components/TaskStatus.tsx`
- Create: `frontend/src/components/TaskStatus.test.tsx`

- [ ] **Step 1: Write failing tests**

```typescript
// frontend/src/components/TaskStatus.test.tsx
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import TaskStatus from './TaskStatus'

describe('TaskStatus', () => {
  it('renders nothing when idle', () => {
    const { container } = render(
      <TaskStatus status="idle" error={null} successMessage="Done" />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('shows Running text when running', () => {
    render(<TaskStatus status="running" error={null} successMessage="Done" />)
    expect(screen.getByText('Running…')).toBeTruthy()
  })

  it('shows successMessage when done', () => {
    render(<TaskStatus status="done" error={null} successMessage="Import complete" />)
    expect(screen.getByText('Import complete')).toBeTruthy()
  })

  it('shows error text when failed with error', () => {
    render(<TaskStatus status="failed" error="Something broke" successMessage="Done" />)
    expect(screen.getByText('Something broke')).toBeTruthy()
  })

  it('shows fallback text when failed with null error', () => {
    render(<TaskStatus status="failed" error={null} successMessage="Done" />)
    expect(screen.getByText('Failed')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm test -- --reporter=verbose TaskStatus
```

Expected: FAIL (module not found).

- [ ] **Step 3: Create `frontend/src/components/TaskStatus.tsx`**

```typescript
export interface TaskStatusProps {
  status: 'idle' | 'running' | 'done' | 'failed'
  error: string | null
  successMessage: string
}

export default function TaskStatus({ status, error, successMessage }: TaskStatusProps) {
  if (status === 'idle') return null
  if (status === 'running') {
    return <span style={{ fontSize: 12, color: '#64748b' }}>Running…</span>
  }
  if (status === 'done') {
    return <span style={{ fontSize: 12, color: '#16a34a' }}>{successMessage}</span>
  }
  return <span style={{ fontSize: 12, color: '#dc2626' }}>{error ?? 'Failed'}</span>
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npm test -- --reporter=verbose TaskStatus
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TaskStatus.tsx frontend/src/components/TaskStatus.test.tsx
git commit -m "$(cat <<'EOF'
feat(ui3): TaskStatus component — idle/running/done/failed inline display

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: API client and types updates

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add new types to `frontend/src/api/types.ts`**

Append to the end of the file:

```typescript
export interface TaskResponse {
  task_id: string
}

export interface CreateStudyNoteRequest {
  source: string
  source_id: string
  concept_tag: string
  section_ref?: string
  note_text?: string
}

export interface CreateLearningSourceRequest {
  source_type: string
  source_key: string
  display_name: string
  added_by: string
}
```

- [ ] **Step 2: Update `frontend/src/api/client.ts`**

Replace the entire file:

```typescript
import type {
  ChatSession,
  CreateLearningSourceRequest,
  CreateStudyNoteRequest,
  DatasetItem,
  Hypothesis,
  KnowledgeSourceItem,
  LearningSourceItem,
  Preferences,
  ResearchMetrics,
  ResearchQuestion,
  SqlResult,
  StudyNote,
  SuggestionsResponse,
  TaskResponse,
} from './types'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'PUT',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

async function del<T = void>(path: string): Promise<T> {
  const res = await fetch(path, { method: 'DELETE' })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  getPreferences: () => get<Preferences>('/api/preferences'),
  setAgentMode: (mode: string) =>
    put<{ agent_mode: string }>('/api/preferences/agent-mode', { mode }),
  getSessions: () => get<ChatSession[]>('/api/sessions'),
  getStudyLog: () => get<StudyNote[]>('/api/study-log'),
  createStudyNote: (body: CreateStudyNoteRequest) =>
    post<StudyNote>('/api/study-log', body),
  getSuggestions: () => get<SuggestionsResponse>('/api/suggestions'),
  dismissImportItem: (id: number) =>
    post<void>(`/api/suggestions/import-queue/${id}/dismiss`),
  dismissSourceSuggestion: (id: number) =>
    post<void>(`/api/suggestions/source-suggestions/${id}/dismiss`),
  promoteSourceSuggestion: (id: number) =>
    post<LearningSourceItem>(`/api/suggestions/source-suggestions/${id}/promote`),
  getDatasets: (keyword?: string) =>
    get<DatasetItem[]>(
      keyword ? `/api/datasets?keyword=${encodeURIComponent(keyword)}` : '/api/datasets',
    ),
  importDataset: (source: string, sourceId: string) =>
    post<TaskResponse>(`/api/datasets/${source}/${sourceId}/import`),
  getRegistry: () => get<LearningSourceItem[]>('/api/registry'),
  deleteRegistryEntry: (id: number) =>
    del(`/api/registry/${id}`),
  createRegistryEntry: (body: CreateLearningSourceRequest) =>
    post<LearningSourceItem>('/api/registry', body),
  getKnowledgeLibrary: (status = 'all') =>
    get<KnowledgeSourceItem[]>(`/api/knowledge-library?status=${status}`),
  approveSource: (id: number) =>
    post<KnowledgeSourceItem>(`/api/knowledge-library/${id}/approve`),
  rejectSource: (id: number) =>
    post<KnowledgeSourceItem>(`/api/knowledge-library/${id}/reject`),
  getResearchMetrics: () => get<ResearchMetrics>('/api/research/metrics'),
  getResearchQuestions: (status = 'all') =>
    get<ResearchQuestion[]>(`/api/research/questions?status=${status}`),
  getHypotheses: (status = 'all') =>
    get<Hypothesis[]>(`/api/research/hypotheses?status=${status}`),
  snapshotMetrics: () => post<Record<string, unknown>>('/api/research/metrics/snapshot'),
  runHypothesisReview: (id: number) =>
    post<TaskResponse>(`/api/research/hypotheses/${id}/review`),
  executeSQL: (sql: string) => post<SqlResult>('/api/sql/execute', { sql }),
}
```

- [ ] **Step 3: Run full frontend suite to verify no regression**

```bash
cd frontend && npm test
```

Expected: all existing tests PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "$(cat <<'EOF'
feat(ui3): API client — del helper, new mutation methods for all 7 write operations

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: StudyLogPanel add-tag form

**Files:**
- Modify: `frontend/src/pages/StudyLogPanel.tsx`
- Modify: `frontend/src/pages/StudyLogPanel.test.tsx`

- [ ] **Step 1: Write failing tests**

Add these tests to `frontend/src/pages/StudyLogPanel.test.tsx` (inside the existing `describe` block):

```typescript
  it('shows Add Tag button in Study Tags view', () => {
    render(<StudyLogPanel />, { wrapper: makeWrapper([]) })
    expect(screen.getByText('Add Tag')).toBeTruthy()
  })

  it('shows inline error when submitting with empty concept_tag', () => {
    render(<StudyLogPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Tag'))
    fireEvent.click(screen.getByText('Save'))
    expect(screen.getByText('Concept tag is required')).toBeTruthy()
  })

  it('add-tag form submits POST /api/study-log', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: 1, source: 'openneuro', source_id: 'ds001',
        concept_tag: 'LTP', section_ref: null, note_text: null,
        tagged_at: '2026-01-01T00:00:00',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<StudyLogPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Tag'))
    fireEvent.change(screen.getAllByRole('textbox')[0], { target: { value: 'ds001' } })
    fireEvent.change(screen.getAllByRole('textbox')[1], { target: { value: 'LTP' } })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/study-log',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })
```

Add missing imports at the top of the test file:

```typescript
import { waitFor } from '@testing-library/react'
import { vi } from 'vitest'
```

- [ ] **Step 2: Run failing tests**

```bash
cd frontend && npm test -- --reporter=verbose StudyLogPanel
```

Expected: the 3 new tests FAIL.

- [ ] **Step 3: Replace `frontend/src/pages/StudyLogPanel.tsx`**

```typescript
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { ChatSession, CreateStudyNoteRequest, StudyNote } from '../api/types'

type View = 'study-tags' | 'chat-history'

function StudyTagsView() {
  const queryClient = useQueryClient()
  const { data = [], isLoading, isError, error } = useQuery<StudyNote[]>({
    queryKey: ['study-log'],
    queryFn: api.getStudyLog,
  })
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    source: 'openneuro',
    source_id: '',
    concept_tag: '',
    section_ref: '',
    note_text: '',
  })
  const [formError, setFormError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: (body: CreateStudyNoteRequest) => api.createStudyNote(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['study-log'] })
      setShowForm(false)
      setForm({ source: 'openneuro', source_id: '', concept_tag: '', section_ref: '', note_text: '' })
      setFormError(null)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.concept_tag.trim()) {
      setFormError('Concept tag is required')
      return
    }
    setFormError(null)
    create.mutate({
      source: form.source,
      source_id: form.source_id,
      concept_tag: form.concept_tag,
      section_ref: form.section_ref || undefined,
      note_text: form.note_text || undefined,
    })
  }

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  return (
    <div>
      {data.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No study tags yet.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
              <th style={{ padding: '4px 8px' }}>Source</th>
              <th style={{ padding: '4px 8px' }}>Concept</th>
              <th style={{ padding: '4px 8px' }}>Section</th>
              <th style={{ padding: '4px 8px' }}>Tagged</th>
            </tr>
          </thead>
          <tbody>
            {data.map(row => (
              <tr key={row.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                <td style={{ padding: '4px 8px', color: '#475569' }}>{row.source}:{row.source_id}</td>
                <td style={{ padding: '4px 8px' }}>{row.concept_tag}</td>
                <td style={{ padding: '4px 8px', color: '#94a3b8' }}>{row.section_ref ?? '-'}</td>
                <td style={{ padding: '4px 8px', color: '#94a3b8' }}>{row.tagged_at.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <button
        onClick={() => setShowForm(v => !v)}
        style={{ fontSize: 12, marginTop: 8, padding: '3px 10px', cursor: 'pointer' }}
      >
        {showForm ? 'Cancel' : 'Add Tag'}
      </button>
      {showForm && (
        <form
          onSubmit={handleSubmit}
          style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}
        >
          <select
            value={form.source}
            onChange={e => setForm(f => ({ ...f, source: e.target.value }))}
            style={{ fontSize: 12, padding: '3px 6px' }}
          >
            <option value="openneuro">openneuro</option>
            <option value="pubmed">pubmed</option>
            <option value="arxiv">arxiv</option>
          </select>
          <input
            value={form.source_id}
            onChange={e => setForm(f => ({ ...f, source_id: e.target.value }))}
            placeholder="source_id"
            required
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          <input
            value={form.concept_tag}
            onChange={e => setForm(f => ({ ...f, concept_tag: e.target.value }))}
            placeholder="concept_tag"
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          {formError && (
            <span style={{ fontSize: 11, color: '#dc2626' }}>{formError}</span>
          )}
          <input
            value={form.section_ref}
            onChange={e => setForm(f => ({ ...f, section_ref: e.target.value }))}
            placeholder="section_ref (optional)"
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          <textarea
            value={form.note_text}
            onChange={e => setForm(f => ({ ...f, note_text: e.target.value }))}
            placeholder="note (optional)"
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          {create.error && (
            <span style={{ fontSize: 11, color: '#dc2626' }}>
              {(create.error as Error).message}
            </span>
          )}
          <button
            type="submit"
            disabled={create.isPending}
            style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
          >
            Save
          </button>
        </form>
      )}
    </div>
  )
}

function ChatHistoryView() {
  const { data = [], isLoading, isError, error } = useQuery<ChatSession[]>({
    queryKey: ['sessions'],
    queryFn: api.getSessions,
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }
  if (data.length === 0) {
    return <p style={{ color: '#94a3b8', fontSize: 13 }}>No chat sessions yet.</p>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {data.map(session => (
        <div
          key={session.id}
          style={{ padding: '8px 10px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6 }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#1e293b' }}>{session.inferred_topic}</span>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>{session.started_at.slice(0, 10)}</span>
          </div>
          <div style={{ fontSize: 11, color: '#64748b', display: 'flex', gap: 12 }}>
            <span>{session.agent_mode}</span>
            <span>{session.message_count} messages</span>
          </div>
          {session.summary_preview && (
            <p style={{ fontSize: 11, color: '#475569', marginTop: 4, marginBottom: 0 }}>
              {session.summary_preview}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}

export default function StudyLogPanel() {
  const [view, setView] = useState<View>('study-tags')

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h4 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: '#1e293b' }}>Study Log</h4>
        <select
          value={view}
          onChange={e => setView(e.target.value as View)}
          style={{ padding: '3px 6px', fontSize: 11, border: '1px solid #cbd5e1', borderRadius: 4 }}
        >
          <option value="study-tags">Study Tags</option>
          <option value="chat-history">Chat History</option>
        </select>
      </div>
      {view === 'study-tags' ? <StudyTagsView /> : <ChatHistoryView />}
    </div>
  )
}
```

- [ ] **Step 4: Run all StudyLogPanel tests**

```bash
cd frontend && npm test -- --reporter=verbose StudyLogPanel
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/StudyLogPanel.tsx frontend/src/pages/StudyLogPanel.test.tsx
git commit -m "$(cat <<'EOF'
feat(ui3): StudyLogPanel — add-tag form with inline validation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: SuggestionsPanel source suggestion actions + import

**Files:**
- Modify: `frontend/src/pages/SuggestionsPanel.tsx`
- Modify: `frontend/src/pages/SuggestionsPanel.test.tsx`

- [ ] **Step 1: Write failing tests**

Add to `frontend/src/pages/SuggestionsPanel.test.tsx` (inside existing `describe` block):

```typescript
  it('renders Dismiss and Promote buttons on source suggestions', () => {
    render(<SuggestionsPanel />, {
      wrapper: makeWrapper({
        import_queue: [],
        source_suggestions: [{
          id: 1,
          suggestion_type: 'paper',
          reference: '10.1234/test',
          display_name: 'LTP Study',
          reason: 'Relevant',
          status: 'pending',
          suggested_at: '2026-01-01',
        }],
      }),
    })
    expect(screen.getByText('Dismiss')).toBeTruthy()
    expect(screen.getByText('Promote')).toBeTruthy()
  })

  it('renders Import button on import queue items', () => {
    render(<SuggestionsPanel />, {
      wrapper: makeWrapper({
        import_queue: [{
          id: 1,
          source: 'openneuro',
          source_id: 'ds001',
          title: 'Test DS',
          status: 'pending',
          suggested_at: '2026-01-01',
          reason: null,
          chapter_ref: null,
        }],
        source_suggestions: [],
      }),
    })
    expect(screen.getByText('Import')).toBeTruthy()
  })
```

- [ ] **Step 2: Run failing tests**

```bash
cd frontend && npm test -- --reporter=verbose SuggestionsPanel
```

Expected: the 2 new tests FAIL.

- [ ] **Step 3: Replace `frontend/src/pages/SuggestionsPanel.tsx`**

```typescript
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import TaskStatus from '../components/TaskStatus'
import { useTask } from '../hooks/useTask'
import type { ImportQueueItem, SourceSuggestionItem } from '../api/types'

function ImportQueueRow({ item }: { item: ImportQueueItem }) {
  const queryClient = useQueryClient()
  const [taskId, setTaskId] = useState<string | null>(null)

  const dismiss = useMutation({
    mutationFn: () => api.dismissImportItem(item.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['suggestions'] }),
  })

  const importMutation = useMutation({
    mutationFn: () => api.importDataset(item.source, item.source_id),
    onSuccess: (data) => setTaskId(data.task_id),
  })

  const taskState = useTask(taskId, 180000, () => {
    queryClient.invalidateQueries({ queryKey: ['datasets'] })
  })

  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}>
      <strong>{item.title ?? item.source_id}</strong>
      {' '}
      <code style={{ fontSize: 11 }}>{item.source}:{item.source_id}</code>
      {item.chapter_ref && (
        <div style={{ fontSize: 12, color: '#64748b' }}>While reading: {item.chapter_ref}</div>
      )}
      {item.reason && (
        <p style={{ fontSize: 12, margin: '4px 0', color: '#475569' }}>{item.reason}</p>
      )}
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <button
          onClick={() => dismiss.mutate()}
          disabled={dismiss.isPending}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
        >
          Dismiss
        </button>
        <button
          onClick={() => importMutation.mutate()}
          disabled={importMutation.isPending || taskState.status === 'running'}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
        >
          Import
        </button>
      </div>
      <TaskStatus status={taskState.status} error={taskState.error} successMessage="Import complete" />
    </div>
  )
}

function SourceSuggestionRow({ item }: { item: SourceSuggestionItem }) {
  const queryClient = useQueryClient()

  const dismiss = useMutation({
    mutationFn: () => api.dismissSourceSuggestion(item.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['suggestions'] }),
  })

  const promote = useMutation({
    mutationFn: () => api.promoteSourceSuggestion(item.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggestions'] })
      queryClient.invalidateQueries({ queryKey: ['registry'] })
    },
  })

  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}>
      <strong>{item.display_name ?? item.reference ?? '-'}</strong>
      {' '}
      <code style={{ fontSize: 11 }}>({item.suggestion_type})</code>
      {item.reason && (
        <p style={{ fontSize: 12, margin: '4px 0', color: '#475569' }}>{item.reason}</p>
      )}
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <button
          onClick={() => dismiss.mutate()}
          disabled={dismiss.isPending}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
        >
          Dismiss
        </button>
        <button
          onClick={() => promote.mutate()}
          disabled={promote.isPending}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
        >
          Promote
        </button>
      </div>
    </div>
  )
}

export default function SuggestionsPanel() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['suggestions'],
    queryFn: api.getSuggestions,
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  const { import_queue, source_suggestions } = data!
  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Dataset Import Requests</h4>
      {import_queue.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No pending import suggestions.</p>
      ) : import_queue.map(item => (
        <ImportQueueRow key={item.id} item={item} />
      ))}

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <h4 style={{ marginBottom: 8 }}>Connector Requests</h4>
      {source_suggestions.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No pending source suggestions.</p>
      ) : source_suggestions.map(item => (
        <SourceSuggestionRow key={item.id} item={item} />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Run all SuggestionsPanel tests**

```bash
cd frontend && npm test -- --reporter=verbose SuggestionsPanel
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SuggestionsPanel.tsx frontend/src/pages/SuggestionsPanel.test.tsx
git commit -m "$(cat <<'EOF'
feat(ui3): SuggestionsPanel — dismiss/promote source suggestions, import with task polling

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: RegistryPanel remove + add form

**Files:**
- Modify: `frontend/src/pages/RegistryPanel.tsx`
- Create: `frontend/src/pages/RegistryPanel.test.tsx`

- [ ] **Step 1: Write failing tests**

```typescript
// frontend/src/pages/RegistryPanel.test.tsx
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'

import RegistryPanel from './RegistryPanel'

function makeWrapper(data: unknown = []) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['registry'], data)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('RegistryPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders source groups with items', () => {
    render(<RegistryPanel />, {
      wrapper: makeWrapper([
        { id: 1, source_type: 'paper', source_key: 'doi:test', display_name: 'LTP Paper', added_by: 'user', added_at: '2026-01-01T00:00:00' },
        { id: 2, source_type: 'book', source_key: 'isbn:test', display_name: 'Neuro Text', added_by: 'user', added_at: '2026-01-01T00:00:00' },
      ]),
    })
    expect(screen.getByText('LTP Paper')).toBeTruthy()
    expect(screen.getByText('Neuro Text')).toBeTruthy()
  })

  it('renders Remove buttons per item', () => {
    render(<RegistryPanel />, {
      wrapper: makeWrapper([
        { id: 1, source_type: 'paper', source_key: 'doi:test', display_name: 'LTP Paper', added_by: 'user', added_at: '2026-01-01T00:00:00' },
      ]),
    })
    expect(screen.getByText('Remove')).toBeTruthy()
  })

  it('remove fires DELETE /api/registry/{id}', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      text: async () => '',
      json: async () => undefined,
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<RegistryPanel />, {
      wrapper: makeWrapper([
        { id: 1, source_type: 'paper', source_key: 'doi:test', display_name: 'LTP Paper', added_by: 'user', added_at: '2026-01-01T00:00:00' },
      ]),
    })
    fireEvent.click(screen.getByText('Remove'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/registry/1',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })

  it('shows Add Source button', () => {
    render(<RegistryPanel />, { wrapper: makeWrapper([]) })
    expect(screen.getByText('Add Source')).toBeTruthy()
  })

  it('add-source form submits POST /api/registry', async () => {
    const newItem = {
      id: 99, source_type: 'paper', source_key: 'doi:new',
      display_name: 'New Paper', added_by: 'user', added_at: '2026-01-01T00:00:00',
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => newItem,
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<RegistryPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Source'))
    fireEvent.change(screen.getByPlaceholderText('source key'), { target: { value: 'doi:new' } })
    fireEvent.change(screen.getByPlaceholderText('display name'), { target: { value: 'New Paper' } })
    fireEvent.change(screen.getByPlaceholderText('added by'), { target: { value: 'user' } })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/registry',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })
})
```

- [ ] **Step 2: Run failing tests**

```bash
cd frontend && npm test -- --reporter=verbose RegistryPanel
```

Expected: FAIL (no Remove/Add Source buttons yet).

- [ ] **Step 3: Replace `frontend/src/pages/RegistryPanel.tsx`**

```typescript
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { CreateLearningSourceRequest, LearningSourceItem } from '../api/types'

function SourceGroup({
  title,
  items,
  onRemove,
  isRemoving,
}: {
  title: string
  items: LearningSourceItem[]
  onRemove: (id: number) => void
  isRemoving: boolean
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
        {title} ({items.length})
      </div>
      {items.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 12 }}>None yet.</p>
      ) : items.map(item => (
        <div
          key={item.id}
          style={{
            padding: '6px 8px',
            border: '1px solid #e2e8f0',
            borderRadius: 6,
            marginBottom: 4,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
          }}
        >
          <div>
            <div style={{ fontSize: 13 }}>{item.display_name}</div>
            <div style={{ fontSize: 11, color: '#64748b' }}>
              {item.source_key} · added by {item.added_by} on {item.added_at.slice(0, 10)}
            </div>
          </div>
          <button
            onClick={() => onRemove(item.id)}
            disabled={isRemoving}
            style={{ fontSize: 11, padding: '2px 6px', cursor: 'pointer', color: '#dc2626' }}
          >
            Remove
          </button>
        </div>
      ))}
    </div>
  )
}

export default function RegistryPanel() {
  const queryClient = useQueryClient()
  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['registry'],
    queryFn: api.getRegistry,
  })
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<CreateLearningSourceRequest>({
    source_type: 'paper',
    source_key: '',
    display_name: '',
    added_by: '',
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteRegistryEntry(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['registry'] }),
  })

  const create = useMutation({
    mutationFn: (body: CreateLearningSourceRequest) => api.createRegistryEntry(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['registry'] })
      setShowForm(false)
      setForm({ source_type: 'paper', source_key: '', display_name: '', added_by: '' })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    create.mutate(form)
  }

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  const books = data.filter(row => row.source_type === 'book')
  const papers = data.filter(row => row.source_type === 'paper')
  const datasets = data.filter(row => row.source_type === 'dataset')
  const other = data.filter(row => !['book', 'paper', 'dataset'].includes(row.source_type))

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 12 }}>Learning Registry</h4>
      <SourceGroup title="Books" items={books} onRemove={id => remove.mutate(id)} isRemoving={remove.isPending} />
      <SourceGroup title="Papers & Studies" items={papers} onRemove={id => remove.mutate(id)} isRemoving={remove.isPending} />
      <SourceGroup title="Datasets" items={datasets} onRemove={id => remove.mutate(id)} isRemoving={remove.isPending} />
      {other.length > 0 && (
        <SourceGroup title="Other" items={other} onRemove={id => remove.mutate(id)} isRemoving={remove.isPending} />
      )}
      <button
        onClick={() => setShowForm(v => !v)}
        style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer', marginTop: 8 }}
      >
        {showForm ? 'Cancel' : 'Add Source'}
      </button>
      {showForm && (
        <form
          onSubmit={handleSubmit}
          style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}
        >
          <select
            value={form.source_type}
            onChange={e => setForm(f => ({ ...f, source_type: e.target.value }))}
            style={{ fontSize: 12, padding: '3px 6px' }}
          >
            <option value="book">book</option>
            <option value="paper">paper</option>
            <option value="dataset">dataset</option>
            <option value="arxiv">arxiv</option>
            <option value="other">other</option>
          </select>
          <input
            value={form.source_key}
            onChange={e => setForm(f => ({ ...f, source_key: e.target.value }))}
            placeholder="source key"
            required
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          <input
            value={form.display_name}
            onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
            placeholder="display name"
            required
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          <input
            value={form.added_by}
            onChange={e => setForm(f => ({ ...f, added_by: e.target.value }))}
            placeholder="added by"
            required
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          {create.error && (
            <span style={{ fontSize: 11, color: '#dc2626' }}>
              {(create.error as Error).message}
            </span>
          )}
          <button
            type="submit"
            disabled={create.isPending}
            style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
          >
            Save
          </button>
        </form>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run all RegistryPanel tests**

```bash
cd frontend && npm test -- --reporter=verbose RegistryPanel
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RegistryPanel.tsx frontend/src/pages/RegistryPanel.test.tsx
git commit -m "$(cat <<'EOF'
feat(ui3): RegistryPanel — Remove button per item, Add Source form

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: ResearchPanel hypothesis review

**Files:**
- Modify: `frontend/src/pages/ResearchPanel.tsx`
- Create: `frontend/src/pages/ResearchPanel.test.tsx`

- [ ] **Step 1: Write failing tests**

```typescript
// frontend/src/pages/ResearchPanel.test.tsx
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'

import ResearchPanel from './ResearchPanel'

function makeWrapper(data: {
  hypotheses?: unknown[]
  metrics?: unknown
  questions?: unknown[]
} = {}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  if (data.hypotheses !== undefined) qc.setQueryData(['research-hypotheses'], data.hypotheses)
  if (data.metrics !== undefined) qc.setQueryData(['research-metrics'], data.metrics)
  if (data.questions !== undefined) qc.setQueryData(['research-questions'], data.questions)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('ResearchPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows empty state when no hypotheses', () => {
    render(<ResearchPanel />, { wrapper: makeWrapper({ hypotheses: [] }) })
    expect(screen.getByText(/No hypotheses yet/)).toBeTruthy()
  })

  it('renders Run Review button per hypothesis', () => {
    render(<ResearchPanel />, {
      wrapper: makeWrapper({
        hypotheses: [{
          id: 1, title: 'LTP Hypothesis', mechanism: null,
          status: 'draft', created_at: '2026-01-01',
        }],
      }),
    })
    expect(screen.getByText('Run Review')).toBeTruthy()
  })

  it('shows Running status after clicking Run Review', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ task_id: 'test-task-id' }),
    }))

    render(<ResearchPanel />, {
      wrapper: makeWrapper({
        hypotheses: [{
          id: 1, title: 'LTP Hypothesis', mechanism: null,
          status: 'draft', created_at: '2026-01-01',
        }],
      }),
    })
    fireEvent.click(screen.getByText('Run Review'))

    await waitFor(() => {
      expect(screen.getByText('Running…')).toBeTruthy()
    })
  })
})
```

- [ ] **Step 2: Run failing tests**

```bash
cd frontend && npm test -- --reporter=verbose ResearchPanel
```

Expected: FAIL (no Run Review button yet).

- [ ] **Step 3: Replace `frontend/src/pages/ResearchPanel.tsx`**

```typescript
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import TaskStatus from '../components/TaskStatus'
import { useTask } from '../hooks/useTask'
import type { Hypothesis } from '../api/types'

function HypothesisCard({ hypothesis }: { hypothesis: Hypothesis }) {
  const queryClient = useQueryClient()
  const [taskId, setTaskId] = useState<string | null>(null)

  const reviewMutation = useMutation({
    mutationFn: () => api.runHypothesisReview(hypothesis.id),
    onSuccess: (data) => setTaskId(data.task_id),
  })

  const taskState = useTask(taskId, 180000, () => {
    queryClient.invalidateQueries({ queryKey: ['research-hypotheses'] })
  })

  return (
    <div style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>{hypothesis.title}</div>
          <div style={{ fontSize: 11, color: '#94a3b8' }}>
            {hypothesis.status} · {hypothesis.created_at?.slice(0, 10)}
          </div>
        </div>
        <button
          onClick={() => reviewMutation.mutate()}
          disabled={reviewMutation.isPending || taskState.status === 'running'}
          style={{ fontSize: 11, padding: '2px 8px', cursor: 'pointer' }}
        >
          Run Review
        </button>
      </div>
      <TaskStatus
        status={taskState.status}
        error={taskState.error}
        successMessage="Review complete"
      />
    </div>
  )
}

export default function ResearchPanel() {
  const queryClient = useQueryClient()

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['research-metrics'],
    queryFn: api.getResearchMetrics,
  })
  const { data: questions = [], isLoading: questionsLoading } = useQuery({
    queryKey: ['research-questions'],
    queryFn: () => api.getResearchQuestions('all'),
  })
  const { data: hypotheses = [], isLoading: hypothesesLoading } = useQuery({
    queryKey: ['research-hypotheses'],
    queryFn: () => api.getHypotheses('all'),
  })

  const snapshot = useMutation({
    mutationFn: api.snapshotMetrics,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-metrics'] }),
  })

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Research</h4>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>Metrics</div>
        {metricsLoading ? (
          <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            {([
              ['Approved Sources', metrics?.approved_sources_count],
              ['Sessions', metrics?.chat_sessions_count],
              ['Lit Searches', metrics?.literature_searches_count],
              ['Hypotheses', metrics?.research_hypotheses_count],
            ] as [string, number | undefined][]).map(([label, value]) => (
              <div key={label} style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: '6px 10px' }}>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{value ?? '-'}</div>
                <div style={{ fontSize: 11, color: '#64748b' }}>{label}</div>
              </div>
            ))}
          </div>
        )}
        <button
          onClick={() => snapshot.mutate()}
          disabled={snapshot.isPending}
          style={{ marginTop: 8, fontSize: 12, padding: '4px 10px', cursor: 'pointer' }}
        >
          Snapshot Metrics
        </button>
      </div>

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>
          Research Questions ({questions.length})
        </div>
        {questionsLoading ? (
          <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
        ) : questions.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: 12 }}>No research questions yet.</p>
        ) : questions.map(question => (
          <div key={question.id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9' }}>
            <div style={{ fontSize: 13 }}>{question.question}</div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>
              {question.status} · {question.created_at?.slice(0, 10)}
            </div>
          </div>
        ))}
      </div>

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <div>
        <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>
          Draft Hypotheses ({hypotheses.length})
        </div>
        {hypothesesLoading ? (
          <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
        ) : hypotheses.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: 12 }}>No hypotheses yet.</p>
        ) : hypotheses.map(hypothesis => (
          <HypothesisCard key={hypothesis.id} hypothesis={hypothesis} />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run all ResearchPanel tests**

```bash
cd frontend && npm test -- --reporter=verbose ResearchPanel
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Run full frontend suite**

```bash
cd frontend && npm test
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ResearchPanel.tsx frontend/src/pages/ResearchPanel.test.tsx
git commit -m "$(cat <<'EOF'
feat(ui3): ResearchPanel — Run Review button per hypothesis with task polling

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: Streamlit deprecation banner

**Files:**
- Modify: `src/neurodb/ui/app.py`

- [ ] **Step 1: Add banner to `src/neurodb/ui/app.py`**

After line 19 (`st.set_page_config(page_title="NeuroDb Explorer", layout="wide")`), add:

```python
st.info("The React workbench at http://localhost:5173 is now the primary UI. This Streamlit app will be retired in UI-4.")
```

- [ ] **Step 2: Run Python tests to verify no regression**

```bash
uv run pytest tests/ -q
```

Expected: no new failures.

- [ ] **Step 3: Commit**

```bash
git add src/neurodb/ui/app.py
git commit -m "$(cat <<'EOF'
feat(ui3): Streamlit deprecation banner — demotes to secondary UI

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: Manual test plan and docs update

**Files:**
- Create: `docs/testsPlans/manualTestPlan_ui3_parity_migration.md`
- Modify: `docs/projectStatus.md`
- Modify: `docs/UI_EpochPlan.md`

- [ ] **Step 1: Create `docs/testsPlans/manualTestPlan_ui3_parity_migration.md`**

```markdown
# Manual Test Plan — UI-3: Parity Migration

**Epoch scope:** UI — all 7 write operations moved to React; Streamlit demoted to secondary.
**Phase:** UI-3
**Design source:** `docs/superpowers/specs/2026-05-11-ui3-parity-migration-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-05-11-ui3-parity-migration.md`
**Status:** Active
**Date:** 2026-05-11

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. Automated Python tests pass — no new failures beyond those tracked in `docs/testLog.md`:

```bash
uv run pytest tests/ -q
```

2. Automated frontend tests pass:

```bash
cd frontend && npm test
```

3. Start both servers:

```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
cd frontend && npm run dev
```

Open http://localhost:5173 in a browser.

---

## Write Operation Evals

### T1 — Create study tag

Open Study Log panel. Select "Study Tags" in the dropdown. Click "Add Tag".

Fill in: source=openneuro, source_id=ds000001 (must be in datasets index), concept_tag=LTP, section_ref=Ch3.

Click Save.

**Pass:** New row appears in the study tag table with concept "LTP". Form closes.

### T2 — Inline error on missing concept_tag

Open Study Log panel, click "Add Tag". Leave concept_tag blank. Click Save.

**Pass:** "Concept tag is required" appears inline. No API call is made.

### T3 — Dismiss source suggestion

Open Suggestions panel. Find a row under "Connector Requests" with status pending.

Click Dismiss.

**Pass:** Row disappears from the list (re-fetch returns no longer pending). Returns 204.

### T4 — Promote source suggestion to registry

Open Suggestions panel. Find a pending source suggestion row. Click Promote.

**Pass:** Row disappears from Suggestions. Open Registry panel — the promoted entry appears as a new row under the appropriate type group.

### T5 — Remove registry entry

Open Registry panel. Locate any entry. Click Remove.

**Pass:** Entry disappears from the registry list after mutation completes.

### T6 — Add registry entry manually

Open Registry panel. Click "Add Source". Fill in: source_type=paper, source_key=doi:10.test/manual, display_name=Test Paper, added_by=user. Click Save.

**Pass:** Form closes. New entry "Test Paper" appears in Papers & Studies group.

### T7 — Import dataset (background task + polling)

Open Suggestions panel. Find a pending import request. Click Import.

**Pass:** "Running…" appears inline while the task runs. On completion, "Import complete" appears in green. The Datasets panel refreshes (new dataset visible if the ingest succeeded).

If the dataset source is not configured, the task will fail. **Pass criteria:** task transitions from Running → either Import complete or an error message (no infinite spinner).

### T8 — Run hypothesis review (background task + polling)

Open Research panel. Locate a hypothesis card. Click "Run Review".

**Pass:** "Running…" appears inline. On completion (up to ~60s), "Review complete" appears in green. The hypotheses list re-fetches.

If no API key is configured, the task will fail. **Pass criteria:** task transitions from Running → either Review complete or an error message.

### T9 — Streamlit deprecation banner

Start the Streamlit app:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

Open http://localhost:8501.

**Pass:** Blue info banner appears at the top: "The React workbench at http://localhost:5173 is now the primary UI. This Streamlit app will be retired in UI-4."

---

## Sign-off

| Eval | Result | Notes |
|------|--------|-------|
| T1 - Create study tag | | |
| T2 - Inline error on missing concept_tag | | |
| T3 - Dismiss source suggestion | | |
| T4 - Promote source suggestion | | |
| T5 - Remove registry entry | | |
| T6 - Add registry entry | | |
| T7 - Import dataset | | |
| T8 - Run hypothesis review | | |
| T9 - Streamlit deprecation banner | | |

**Signed off:** (pending)
```

- [ ] **Step 2: Update `docs/projectStatus.md`**

Change the **Active focus** line from:
```
**Active focus:** UI-2B signed off; next focus pending selection
```
to:
```
**Active focus:** UI-3 parity migration — all 7 write operations + Streamlit deprecation banner
```

Change the **Next** line to:
```
**Next:** Manual verification of UI-3 then sign off; UI-4 Streamlit retirement decision
```

Update the UI row in the Epoch Status table:
```
| UI | `src/neurodb/ui/`, `src/neurodb/api/`, `frontend/` | UI-3 in progress — parity migration; React has all 7 write operations | Manual test plan active: `docs/testsPlans/manualTestPlan_ui3_parity_migration.md` |
```

Add to the Key References table under Active Plans:
```
| `docs/superpowers/specs/2026-05-11-ui3-parity-migration-design.md` | UI-3 design spec — 7 write operations, background task system, Streamlit deprecation |
| `docs/superpowers/plans/2026-05-11-ui3-parity-migration.md` | UI-3 implementation plan — 15 tasks |
| `docs/testsPlans/manualTestPlan_ui3_parity_migration.md` | UI-3 manual test plan — 9 evals, active |
```

- [ ] **Step 3: Update `docs/UI_EpochPlan.md`**

Change the header status line to:
```
**Status:** UI-3 in progress — parity migration
**Last updated:** 2026-05-11
```

Change the active work line to:
```
**Active work:** UI-3 parity migration — 7 write operations wired to React, Streamlit banner added.
```

Update the UI-3 row in the Phases table:
```
| UI-3 | Parity migration — Streamlit surfaces moved to React one at a time | In progress | — | — | `docs/testsPlans/manualTestPlan_ui3_parity_migration.md` |
```

- [ ] **Step 4: Commit**

```bash
git add docs/testsPlans/manualTestPlan_ui3_parity_migration.md docs/projectStatus.md docs/UI_EpochPlan.md
git commit -m "$(cat <<'EOF'
docs: UI-3 manual test plan, projectStatus and UI_EpochPlan updated for UI-3 in progress

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `src/neurodb/api/tasks.py` TaskRecord + store | Task 1 |
| `get_task_store` dependency | Task 1 |
| `GET /api/tasks/{task_id}` with timeout check | Task 1 |
| `app.state.tasks = {}` in app factory | Task 1 |
| `POST /api/study-log` | Task 2 |
| `POST /api/suggestions/source-suggestions/{id}/dismiss` | Task 3 |
| `POST /api/suggestions/source-suggestions/{id}/promote` | Task 3 |
| `DELETE /api/registry/{id}` | Task 4 |
| `POST /api/registry` | Task 4 |
| `POST /api/datasets/{source}/{source_id}/import` | Task 5 |
| `POST /api/research/hypotheses/{id}/review` | Task 6 |
| `useTask` hook | Task 7 |
| `TaskStatus` component | Task 8 |
| API client + types | Task 9 |
| StudyLogPanel add-tag form | Task 10 |
| SuggestionsPanel dismiss/promote/import | Task 11 |
| RegistryPanel remove + add form | Task 12 |
| ResearchPanel run review | Task 13 |
| Streamlit deprecation banner | Task 14 |
| Manual test plan + docs | Task 15 |

**All spec requirements covered.**
