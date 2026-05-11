# UI-2 React Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the NeuroDb UI from Streamlit to a Vite + React SPA consuming the FastAPI backend, with all 7 panels functional and the same two-column layout as Streamlit.

**Architecture:** Phase 1 adds 7 new FastAPI route files + schemas + tests. Phase 2 scaffolds the Vite + React project, wires all routes via a typed API client, and implements all panels using TanStack Query. These are two independent build systems (pytest / Vitest) but one deliverable.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic (backend); Vite 6, React 18, React Router v7, TanStack Query v5, TypeScript, Vitest (frontend).

---

## File Map

### Backend (new)
| File | Purpose |
|------|---------|
| `src/neurodb/api/schemas/study_log.py` | `StudyNoteItem` Pydantic model |
| `src/neurodb/api/routes/study_log.py` | `GET /api/study-log` |
| `src/neurodb/api/schemas/sessions.py` | `ChatSessionItem` Pydantic model |
| `src/neurodb/api/routes/sessions.py` | `GET /api/sessions` |
| `src/neurodb/api/schemas/suggestions.py` | `ImportQueueItem`, `SourceSuggestionItem`, `SuggestionsResponse` |
| `src/neurodb/api/routes/suggestions.py` | `GET /api/suggestions`, `POST /api/suggestions/import-queue/{id}/dismiss` |
| `src/neurodb/api/schemas/datasets.py` | `DatasetItem` |
| `src/neurodb/api/routes/datasets.py` | `GET /api/datasets` |
| `src/neurodb/api/schemas/registry.py` | `LearningSourceItem` |
| `src/neurodb/api/routes/registry.py` | `GET /api/registry` |
| `src/neurodb/api/schemas/knowledge_library.py` | `KnowledgeSourceItem` |
| `src/neurodb/api/routes/knowledge_library.py` | `GET /api/knowledge-library`, `POST /{id}/approve`, `POST /{id}/reject` |
| `src/neurodb/api/schemas/sql.py` | `SqlQuery`, `SqlResult` |
| `src/neurodb/api/routes/sql.py` | `POST /api/sql/execute` |
| `tests/unit/test_api_study_log.py` | Tests for study-log route |
| `tests/unit/test_api_sessions.py` | Tests for sessions route |
| `tests/unit/test_api_suggestions.py` | Tests for suggestions route |
| `tests/unit/test_api_datasets.py` | Tests for datasets route |
| `tests/unit/test_api_registry.py` | Tests for registry route |
| `tests/unit/test_api_knowledge_library.py` | Tests for knowledge-library route |
| `tests/unit/test_api_sql.py` | Tests for sql route |

### Backend (modified)
| File | Change |
|------|--------|
| `src/neurodb/api/app.py` | Wire 7 new routers; mount `StaticFiles` if `frontend/dist` exists |

### Frontend (new — all under `frontend/`)
| File | Purpose |
|------|---------|
| `package.json` | npm manifest with all dependencies |
| `vite.config.ts` | Vite config: React plugin, `/api` proxy to port 8001, WSL2 polling |
| `tsconfig.json` | TypeScript config for React/Vite |
| `index.html` | HTML entry point |
| `src/main.tsx` | Root: `QueryClientProvider` + `RouterProvider` |
| `src/App.tsx` | Layout: sidebar, chat column, panel area with `<Routes>` |
| `src/api/types.ts` | TypeScript interfaces for all API responses |
| `src/api/client.ts` | Typed fetch wrappers (`get`, `post`) |
| `src/hooks/useChat.ts` | SSE streaming hook |
| `src/components/Sidebar.tsx` | Mode dropdown + session list |
| `src/components/PanelNav.tsx` | Tab bar with `<NavLink>` |
| `src/components/ChatPanel.tsx` | Message list + input form |
| `src/components/MessageBubble.tsx` | Single message bubble |
| `src/pages/SuggestionsPanel.tsx` | Import queue + source suggestions |
| `src/pages/StudyLogPanel.tsx` | Study tags list |
| `src/pages/DatasetsPanel.tsx` | Dataset search and list |
| `src/pages/RegistryPanel.tsx` | Learning sources grouped by type |
| `src/pages/KnowledgeLibraryPanel.tsx` | Knowledge sources with approve/reject |
| `src/pages/ResearchPanel.tsx` | Metrics, questions, hypotheses |
| `src/pages/SqlPanel.tsx` | SQL textarea + execute |
| `src/test-setup.ts` | `@testing-library/jest-dom` import |
| `src/hooks/useChat.test.ts` | Vitest tests for useChat |
| `src/pages/SuggestionsPanel.test.tsx` | Vitest tests for SuggestionsPanel |
| `src/pages/KnowledgeLibraryPanel.test.tsx` | Vitest tests for KnowledgeLibraryPanel |

---

## Progress

| Task | Status | Commit |
|------|--------|--------|
| Task 1: Study-log route and schema | ✅ Complete | `eb4bf2a` |
| Task 2: Sessions route and schema | ✅ Complete | `3a646c0` |
| Task 3: Suggestions route and schema | In progress | — |
| Task 4: Datasets route and schema | Pending | — |
| Task 5: Registry route and schema | Pending | — |
| Task 6: Knowledge Library route and schema | Pending | — |
| Task 7: SQL route and schema | Pending | — |
| Task 8: Wire new routes in app.py + StaticFiles mount | Pending | — |
| Task 9: Vite + React project scaffold | Pending | — |
| Task 10: API client layer | Pending | — |
| Task 11: useChat hook | Pending | — |
| Task 12: App layout, Sidebar, PanelNav, ChatPanel, MessageBubble | Pending | — |
| Task 13: SuggestionsPanel | Pending | — |
| Task 14: StudyLogPanel | Pending | — |
| Task 15: DatasetsPanel | Pending | — |
| Task 16: RegistryPanel | Pending | — |
| Task 17: KnowledgeLibraryPanel | Pending | — |
| Task 18: ResearchPanel and SqlPanel | Pending | — |
| Task 19: Integration check and manual test plan | Pending | — |

**Current task:** Task 3 — Suggestions route and schema

---

## Patterns Established (Tasks 1–2)

These conventions were confirmed during code review. All future route tasks must follow them:

1. **`response_model=` on all GET decorators** — always `@router.get("/path", response_model=list[SchemaType])`. The return type annotation alone is not sufficient.
2. **All imports at module level in test files** — no `import` statements inside function bodies, including `_insert_*` helpers.
3. **No app.py changes in individual route tasks** — router registration is Task 8 only. Do not touch `src/neurodb/api/app.py` in Tasks 1–7.
4. **DatasetIndex fixture** — `DatasetIndex` has `UniqueConstraint(source, source_id)`. Test fixtures must use lookup-or-create to avoid constraint violations. See `tests/unit/test_api_study_log.py` for the working pattern.
5. **Schema `from_attributes`** — use `model_config = {"from_attributes": True}` when serializing ORM instances via `model_validate`. Use plain `BaseModel` (no `from_attributes`) when using `**row` dict unpacking.
6. **Reference implementations** — `src/neurodb/api/routes/preferences.py` + `tests/unit/test_api_preferences.py`.

---

## Task 1: Study-log route and schema

**Status: ✅ COMPLETE** (commits `ddedd2e`, `eb4bf2a`)

**Files:**
- Create: `src/neurodb/api/schemas/study_log.py`
- Create: `src/neurodb/api/routes/study_log.py`
- Create: `tests/unit/test_api_study_log.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_api_study_log.py
"""Tests for GET /api/study-log route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.study_log import router


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_note(engine, concept_tag: str):
    from neurodb.schema import IngestRun, DatasetIndex, StudyNote
    from neurodb.db import get_session
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1", notes=None)
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        session.add(idx)
        session.flush()
        session.add(StudyNote(index_id=idx.id, concept_tag=concept_tag, tagged_at="2026-01-01T00:00:00"))


def test_get_study_log_empty():
    client, _ = _make_client()
    resp = client.get("/api/study-log")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_study_log_returns_notes():
    client, engine = _make_client()
    _insert_note(engine, "LTP")
    resp = client.get("/api/study-log")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["concept_tag"] == "LTP"
    assert data[0]["source"] == "openneuro"
    assert "id" in data[0]


def test_get_study_log_multiple_notes():
    client, engine = _make_client()
    _insert_note(engine, "LTP")
    _insert_note(engine, "LTD")
    resp = client.get("/api/study-log")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_study_log.py -v
```
Expected: ImportError (module not found)

- [ ] **Step 3: Create schema**

```python
# src/neurodb/api/schemas/study_log.py
from __future__ import annotations
from pydantic import BaseModel


class StudyNoteItem(BaseModel):
    id: int
    source: str
    source_id: str
    concept_tag: str
    section_ref: str | None = None
    note_text: str | None = None
    tagged_at: str
```

- [ ] **Step 4: Create route**

```python
# src/neurodb/api/routes/study_log.py
"""GET /api/study-log route."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.study_log import StudyNoteItem
from neurodb.db import get_session
from neurodb.study import list_tags

router = APIRouter()


@router.get("/study-log")
def get_study_log(engine: Engine = Depends(get_engine)) -> list[StudyNoteItem]:
    with get_session(engine) as session:
        return [StudyNoteItem(**row) for row in list_tags(session)]
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_api_study_log.py -v
```
Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/api/schemas/study_log.py src/neurodb/api/routes/study_log.py tests/unit/test_api_study_log.py
git commit -m "feat: GET /api/study-log route"
```

---

## Task 2: Sessions route and schema

**Status: ✅ COMPLETE** (commits `6e48f59`, `3a646c0`)

**Files:**
- Create: `src/neurodb/api/schemas/sessions.py`
- Create: `src/neurodb/api/routes/sessions.py`
- Create: `tests/unit/test_api_sessions.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_api_sessions.py
"""Tests for GET /api/sessions route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.sessions import router


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_session(engine, topic: str, mode: str = "local_db"):
    from neurodb.schema import ChatSession
    from neurodb.db import get_session
    with get_session(engine) as session:
        session.add(ChatSession(
            session_id=f"sess-{topic}",
            inferred_topic=topic,
            agent_mode=mode,
            started_at="2026-01-01T00:00:00",
            message_count=3,
        ))


def test_get_sessions_empty():
    client, _ = _make_client()
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_sessions_returns_rows():
    client, engine = _make_client()
    _insert_session(engine, "LTP basics")
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["inferred_topic"] == "LTP basics"
    assert data[0]["agent_mode"] == "local_db"
    assert "session_id" in data[0]


def test_get_sessions_ordered_most_recent_first():
    client, engine = _make_client()
    from neurodb.schema import ChatSession
    from neurodb.db import get_session
    with get_session(engine) as session:
        session.add(ChatSession(session_id="a", inferred_topic="older", agent_mode="local_db",
                                started_at="2026-01-01T00:00:00", message_count=1))
        session.add(ChatSession(session_id="b", inferred_topic="newer", agent_mode="local_db",
                                started_at="2026-02-01T00:00:00", message_count=1))
    resp = client.get("/api/sessions")
    data = resp.json()
    assert data[0]["inferred_topic"] == "newer"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_sessions.py -v
```
Expected: ImportError

- [ ] **Step 3: Create schema and route**

```python
# src/neurodb/api/schemas/sessions.py
from __future__ import annotations
from pydantic import BaseModel


class ChatSessionItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    session_id: str
    inferred_topic: str
    agent_mode: str
    started_at: str
    message_count: int
    summary_preview: str | None = None
```

```python
# src/neurodb/api/routes/sessions.py
"""GET /api/sessions route."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.sessions import ChatSessionItem
from neurodb.db import get_session
from neurodb.schema import ChatSession

router = APIRouter()


@router.get("/sessions")
def get_sessions(engine: Engine = Depends(get_engine)) -> list[ChatSessionItem]:
    with get_session(engine) as session:
        rows = (
            session.query(ChatSession)
            .order_by(ChatSession.started_at.desc())
            .all()
        )
        return [ChatSessionItem.model_validate(r) for r in rows]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_api_sessions.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/schemas/sessions.py src/neurodb/api/routes/sessions.py tests/unit/test_api_sessions.py
git commit -m "feat: GET /api/sessions route"
```

---

## Task 3: Suggestions route and schema

**Files:**
- Create: `src/neurodb/api/schemas/suggestions.py`
- Create: `src/neurodb/api/routes/suggestions.py`
- Create: `tests/unit/test_api_suggestions.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_api_suggestions.py
"""Tests for /api/suggestions routes."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.suggestions import router


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/suggestions")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_import_item(engine, source_id="ds001", status="pending"):
    from neurodb.schema import ImportQueue
    from neurodb.db import get_session
    with get_session(engine) as session:
        session.add(ImportQueue(
            source="openneuro", source_id=source_id, title="Test Dataset",
            status=status, suggested_at="2026-01-01T00:00:00",
        ))


def _insert_source_suggestion(engine, display_name="Some Paper", status="pending"):
    from neurodb.schema import SourceSuggestion
    from neurodb.db import get_session
    with get_session(engine) as session:
        session.add(SourceSuggestion(
            suggestion_type="paper", display_name=display_name,
            status=status, suggested_at="2026-01-01T00:00:00",
        ))


def test_get_suggestions_empty():
    client, _ = _make_client()
    resp = client.get("/api/suggestions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["import_queue"] == []
    assert data["source_suggestions"] == []


def test_get_suggestions_returns_pending_only():
    client, engine = _make_client()
    _insert_import_item(engine, "ds001", "pending")
    _insert_import_item(engine, "ds002", "dismissed")
    resp = client.get("/api/suggestions")
    data = resp.json()
    assert len(data["import_queue"]) == 1
    assert data["import_queue"][0]["source_id"] == "ds001"


def test_get_suggestions_includes_source_suggestions():
    client, engine = _make_client()
    _insert_source_suggestion(engine, "LTP Paper")
    resp = client.get("/api/suggestions")
    data = resp.json()
    assert len(data["source_suggestions"]) == 1
    assert data["source_suggestions"][0]["display_name"] == "LTP Paper"


def test_dismiss_import_item_sets_dismissed():
    client, engine = _make_client()
    _insert_import_item(engine, "ds001", "pending")
    item_id = client.get("/api/suggestions").json()["import_queue"][0]["id"]
    resp = client.post(f"/api/suggestions/import-queue/{item_id}/dismiss")
    assert resp.status_code == 204
    # Item no longer in pending list
    data = client.get("/api/suggestions").json()
    assert data["import_queue"] == []


def test_dismiss_import_item_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/suggestions/import-queue/9999/dismiss")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_suggestions.py -v
```
Expected: ImportError

- [ ] **Step 3: Create schema and route**

```python
# src/neurodb/api/schemas/suggestions.py
from __future__ import annotations
from pydantic import BaseModel


class ImportQueueItem(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    source: str
    source_id: str
    title: str | None = None
    reason: str | None = None
    chapter_ref: str | None = None
    status: str
    suggested_at: str


class SourceSuggestionItem(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    suggestion_type: str
    reference: str | None = None
    display_name: str | None = None
    reason: str | None = None
    status: str
    suggested_at: str


class SuggestionsResponse(BaseModel):
    import_queue: list[ImportQueueItem]
    source_suggestions: list[SourceSuggestionItem]
```

```python
# src/neurodb/api/routes/suggestions.py
"""GET /api/suggestions and POST dismiss routes."""
from __future__ import annotations
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.suggestions import ImportQueueItem, SourceSuggestionItem, SuggestionsResponse
from neurodb.db import get_session
from neurodb.schema import ImportQueue, SourceSuggestion

router = APIRouter()


@router.get("")
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
            import_queue=[ImportQueueItem.model_validate(r) for r in import_items],
            source_suggestions=[SourceSuggestionItem.model_validate(r) for r in source_items],
        )


@router.post("/import-queue/{item_id}/dismiss", status_code=204)
def dismiss_import_item(item_id: int, engine: Engine = Depends(get_engine)) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_session(engine) as session:
        row = session.get(ImportQueue, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"ImportQueue item {item_id} not found")
        row.status = "dismissed"
        row.resolved_at = now
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_api_suggestions.py -v
```
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/schemas/suggestions.py src/neurodb/api/routes/suggestions.py tests/unit/test_api_suggestions.py
git commit -m "feat: GET /api/suggestions and dismiss route"
```

---

## Task 4: Datasets route and schema

**Files:**
- Create: `src/neurodb/api/schemas/datasets.py`
- Create: `src/neurodb/api/routes/datasets.py`
- Create: `tests/unit/test_api_datasets.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_api_datasets.py
"""Tests for GET /api/datasets route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.datasets import router


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/datasets")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_dataset(engine, source="openneuro", source_id="ds001"):
    from neurodb.schema import IngestRun, DatasetIndex
    from neurodb.db import get_session
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1", notes=None)
        session.add(run)
        session.flush()
        session.add(DatasetIndex(source=source, source_id=source_id, run_id=run.id))


def test_get_datasets_empty():
    client, _ = _make_client()
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_datasets_returns_rows():
    client, engine = _make_client()
    _insert_dataset(engine, "openneuro", "ds001")
    resp = client.get("/api/datasets")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source"] == "openneuro"
    assert data[0]["source_id"] == "ds001"


def test_get_datasets_keyword_filter():
    client, engine = _make_client()
    _insert_dataset(engine, "openneuro", "ds001")
    _insert_dataset(engine, "dandi", "000123")
    resp = client.get("/api/datasets?keyword=ds0")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source_id"] == "ds001"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_datasets.py -v
```
Expected: ImportError

- [ ] **Step 3: Create schema and route**

```python
# src/neurodb/api/schemas/datasets.py
from __future__ import annotations
from pydantic import BaseModel


class DatasetItem(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    source: str
    source_id: str
```

```python
# src/neurodb/api/routes/datasets.py
"""GET /api/datasets route."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.datasets import DatasetItem
from neurodb.db import get_session
from neurodb.schema import DatasetIndex

router = APIRouter()


@router.get("")
def get_datasets(
    keyword: str | None = None,
    engine: Engine = Depends(get_engine),
) -> list[DatasetItem]:
    with get_session(engine) as session:
        q = session.query(DatasetIndex)
        if keyword:
            q = q.filter(DatasetIndex.source_id.ilike(f"%{keyword}%"))
        rows = q.order_by(DatasetIndex.source).limit(200).all()
        return [DatasetItem.model_validate(r) for r in rows]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_api_datasets.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/schemas/datasets.py src/neurodb/api/routes/datasets.py tests/unit/test_api_datasets.py
git commit -m "feat: GET /api/datasets route"
```

---

## Task 5: Registry route and schema

**Files:**
- Create: `src/neurodb/api/schemas/registry.py`
- Create: `src/neurodb/api/routes/registry.py`
- Create: `tests/unit/test_api_registry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_api_registry.py
"""Tests for GET /api/registry route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.registry import router


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


def _insert_source(engine, source_type="book", display_name="Test Book"):
    from neurodb.schema import LearningSource
    from neurodb.db import get_session
    with get_session(engine) as session:
        session.add(LearningSource(
            source_type=source_type,
            source_key=f"key-{display_name}",
            display_name=display_name,
            added_by="user",
            added_at="2026-01-01T00:00:00",
        ))


def test_get_registry_empty():
    client, _ = _make_client()
    resp = client.get("/api/registry")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_registry_returns_rows():
    client, engine = _make_client()
    _insert_source(engine, "book", "Neuroscience by Purves")
    resp = client.get("/api/registry")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["display_name"] == "Neuroscience by Purves"
    assert data[0]["source_type"] == "book"


def test_get_registry_ordered_by_type_then_name():
    client, engine = _make_client()
    _insert_source(engine, "paper", "Z Paper")
    _insert_source(engine, "book", "A Book")
    resp = client.get("/api/registry")
    data = resp.json()
    assert data[0]["source_type"] == "book"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_registry.py -v
```
Expected: ImportError

- [ ] **Step 3: Create schema and route**

```python
# src/neurodb/api/schemas/registry.py
from __future__ import annotations
from pydantic import BaseModel


class LearningSourceItem(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    source_type: str
    source_key: str
    display_name: str
    added_by: str
    added_at: str
```

```python
# src/neurodb/api/routes/registry.py
"""GET /api/registry route."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.registry import LearningSourceItem
from neurodb.db import get_session
from neurodb.schema import LearningSource

router = APIRouter()


@router.get("")
def get_registry(engine: Engine = Depends(get_engine)) -> list[LearningSourceItem]:
    with get_session(engine) as session:
        rows = (
            session.query(LearningSource)
            .order_by(LearningSource.source_type, LearningSource.display_name)
            .all()
        )
        return [LearningSourceItem.model_validate(r) for r in rows]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_api_registry.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/schemas/registry.py src/neurodb/api/routes/registry.py tests/unit/test_api_registry.py
git commit -m "feat: GET /api/registry route"
```

---

## Task 6: Knowledge Library route and schema

**Files:**
- Create: `src/neurodb/api/schemas/knowledge_library.py`
- Create: `src/neurodb/api/routes/knowledge_library.py`
- Create: `tests/unit/test_api_knowledge_library.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_api_knowledge_library.py
"""Tests for /api/knowledge-library routes."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.knowledge_library import router


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/knowledge-library")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_source(engine, title="Test Source", status="pending"):
    from neurodb.schema import KnowledgeSource
    from neurodb.db import get_session
    with get_session(engine) as session:
        session.add(KnowledgeSource(
            title=title,
            normalized_title=title.lower(),
            source_type="paper",
            topic_context="neuroscience",
            status=status,
            queued_at="2026-01-01T00:00:00",
        ))


def test_get_knowledge_library_empty():
    client, _ = _make_client()
    resp = client.get("/api/knowledge-library")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_knowledge_library_returns_all_by_default():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    _insert_source(engine, "Paper B", "approved")
    resp = client.get("/api/knowledge-library")
    assert len(resp.json()) == 2


def test_get_knowledge_library_filter_by_status():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    _insert_source(engine, "Paper B", "approved")
    resp = client.get("/api/knowledge-library?status=pending")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Paper A"


def test_approve_source_sets_status():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]
    resp = client.post(f"/api/knowledge-library/{source_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["reviewed_at"] is not None


def test_reject_source_sets_status():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]
    resp = client.post(f"/api/knowledge-library/{source_id}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_approve_source_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/knowledge-library/9999/approve")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_knowledge_library.py -v
```
Expected: ImportError

- [ ] **Step 3: Create schema and route**

```python
# src/neurodb/api/schemas/knowledge_library.py
from __future__ import annotations
from pydantic import BaseModel


class KnowledgeSourceItem(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    title: str
    doi: str | None = None
    url: str | None = None
    source_type: str
    topic_context: str
    status: str
    queued_at: str
    reviewed_at: str | None = None
    summary: str | None = None
```

```python
# src/neurodb/api/routes/knowledge_library.py
"""GET /api/knowledge-library and approve/reject routes."""
from __future__ import annotations
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.knowledge_library import KnowledgeSourceItem
from neurodb.db import get_session
from neurodb.schema import KnowledgeSource

router = APIRouter()


@router.get("")
def get_knowledge_library(
    status: str = "all",
    engine: Engine = Depends(get_engine),
) -> list[KnowledgeSourceItem]:
    with get_session(engine) as session:
        q = session.query(KnowledgeSource)
        if status != "all":
            q = q.filter(KnowledgeSource.status == status)
        rows = q.order_by(KnowledgeSource.queued_at.desc()).all()
        return [KnowledgeSourceItem.model_validate(r) for r in rows]


@router.post("/{source_id}/approve")
def approve_source(source_id: int, engine: Engine = Depends(get_engine)) -> KnowledgeSourceItem:
    now = datetime.now(timezone.utc).isoformat()
    with get_session(engine) as session:
        row = session.get(KnowledgeSource, source_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"KnowledgeSource {source_id} not found")
        row.status = "approved"
        row.reviewed_at = now
        session.flush()
        return KnowledgeSourceItem.model_validate(row)


@router.post("/{source_id}/reject")
def reject_source(source_id: int, engine: Engine = Depends(get_engine)) -> KnowledgeSourceItem:
    now = datetime.now(timezone.utc).isoformat()
    with get_session(engine) as session:
        row = session.get(KnowledgeSource, source_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"KnowledgeSource {source_id} not found")
        row.status = "rejected"
        row.reviewed_at = now
        session.flush()
        return KnowledgeSourceItem.model_validate(row)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_api_knowledge_library.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/schemas/knowledge_library.py src/neurodb/api/routes/knowledge_library.py tests/unit/test_api_knowledge_library.py
git commit -m "feat: GET /api/knowledge-library and approve/reject routes"
```

---

## Task 7: SQL route and schema

**Files:**
- Create: `src/neurodb/api/schemas/sql.py`
- Create: `src/neurodb/api/routes/sql.py`
- Create: `tests/unit/test_api_sql.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_api_sql.py
"""Tests for POST /api/sql/execute route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.sql import router


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/sql")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def test_execute_simple_query():
    client, _ = _make_client()
    resp = client.post("/api/sql/execute", json={"sql": "SELECT 1 AS n"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["columns"] == ["n"]
    assert data["rows"] == [[1]]
    assert data["row_count"] == 1


def test_execute_query_against_table():
    client, _ = _make_client()
    resp = client.post("/api/sql/execute", json={"sql": "SELECT * FROM ingest_runs LIMIT 5"})
    assert resp.status_code == 200
    data = resp.json()
    assert "columns" in data
    assert data["rows"] == []


def test_execute_invalid_sql_returns_400():
    client, _ = _make_client()
    resp = client.post("/api/sql/execute", json={"sql": "NOT VALID SQL !!!"})
    assert resp.status_code == 400
    assert "detail" in resp.json()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_sql.py -v
```
Expected: ImportError

- [ ] **Step 3: Create schema and route**

```python
# src/neurodb/api/schemas/sql.py
from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class SqlQuery(BaseModel):
    sql: str


class SqlResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
```

```python
# src/neurodb/api/routes/sql.py
"""POST /api/sql/execute route."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, text

from neurodb.api.deps import get_engine
from neurodb.api.schemas.sql import SqlQuery, SqlResult

router = APIRouter()


@router.post("/execute")
def execute_sql(body: SqlQuery, engine: Engine = Depends(get_engine)) -> SqlResult:
    try:
        with engine.connect() as conn:
            result = conn.execute(text(body.sql))
            rows = result.fetchmany(500)
            cols = list(result.keys())
        return SqlResult(columns=cols, rows=[list(r) for r in rows], row_count=len(rows))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_api_sql.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/schemas/sql.py src/neurodb/api/routes/sql.py tests/unit/test_api_sql.py
git commit -m "feat: POST /api/sql/execute route"
```

---

## Task 8: Wire new routes in app.py and add StaticFiles mount

**Files:**
- Modify: `src/neurodb/api/app.py`
- Test: run full pytest suite

- [ ] **Step 1: Update `create_app` to include all new routers**

Replace the router include block in `create_app` in `src/neurodb/api/app.py`:

```python
"""FastAPI app factory."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import Engine


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

    from neurodb.api.routes import (
        status, preferences, research, chat,
        study_log, sessions, suggestions, datasets,
        registry, knowledge_library, sql,
    )

    app.include_router(status.router, prefix="/api")
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

    _dist = Path("frontend/dist")
    if _dist.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")

    return app


def app_factory() -> FastAPI:
    """Zero-arg factory for uvicorn --factory.

    Usage: uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
    DB path read from NEURODB_DB_PATH env var, defaulting to neurodb.duckdb.
    """
    from dotenv import load_dotenv
    from neurodb.db import create_views, get_engine, init_db

    load_dotenv()
    db_path = os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb")
    engine = get_engine(f"duckdb:///{db_path}")
    init_db(engine)
    create_views(engine)
    return create_app(engine)
```

- [ ] **Step 2: Run full pytest suite**

```bash
uv run pytest tests/ -q
```
Expected: all existing tests pass, plus 28 new ones from Tasks 1–7 (total ~436+)

- [ ] **Step 3: Commit**

```bash
git add src/neurodb/api/app.py
git commit -m "feat: wire 7 new routes in app factory; add StaticFiles mount"
```

---

## Task 9: Vite + React project scaffold

**Files:** All under `frontend/`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/test-setup.ts`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "neurodb-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^7.6.0",
    "@tanstack/react-query": "^5.64.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.2",
    "vite": "^6.3.5",
    "vitest": "^3.1.0",
    "jsdom": "^26.0.0",
    "@testing-library/react": "^16.3.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/user-event": "^14.5.2"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
    watch: {
      usePolling: true,
      interval: 100,
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
  build: {
    outDir: 'dist',
  },
})
```

- [ ] **Step 3: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NeuroDb</title>
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: system-ui, sans-serif; font-size: 14px; }
    </style>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `frontend/src/test-setup.ts`**

```ts
import '@testing-library/jest-dom'
```

- [ ] **Step 6: Create `frontend/src/main.tsx`** (placeholder App for now)

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'

const queryClient = new QueryClient()

function Placeholder() {
  return <div style={{ padding: 16 }}>NeuroDb UI loading…</div>
}

const router = createBrowserRouter([{ path: '/*', element: <Placeholder /> }])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
)
```

- [ ] **Step 7: Install dependencies**

```bash
cd frontend && npm install
```
Expected: `node_modules/` created, no errors

- [ ] **Step 8: Verify dev server starts**

```bash
cd frontend && npm run dev
```
Expected: `Local: http://localhost:5173/` — browser shows "NeuroDb UI loading…". Stop with Ctrl+C.

- [ ] **Step 9: Verify Vitest runs**

```bash
cd frontend && npm test
```
Expected: "No test files found" or 0 tests — no errors

- [ ] **Step 10: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold Vite + React project in frontend/"
```

---

## Task 10: API client layer

**Files:**
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`

- [ ] **Step 1: Create `frontend/src/api/types.ts`**

```ts
export interface StudyNote {
  id: number
  source: string
  source_id: string
  concept_tag: string
  section_ref: string | null
  note_text: string | null
  tagged_at: string
}

export interface ChatSession {
  id: number
  session_id: string
  inferred_topic: string
  agent_mode: string
  started_at: string
  message_count: number
  summary_preview: string | null
}

export interface ImportQueueItem {
  id: number
  source: string
  source_id: string
  title: string | null
  reason: string | null
  chapter_ref: string | null
  status: string
  suggested_at: string
}

export interface SourceSuggestionItem {
  id: number
  suggestion_type: string
  reference: string | null
  display_name: string | null
  reason: string | null
  status: string
  suggested_at: string
}

export interface SuggestionsResponse {
  import_queue: ImportQueueItem[]
  source_suggestions: SourceSuggestionItem[]
}

export interface DatasetItem {
  id: number
  source: string
  source_id: string
}

export interface LearningSourceItem {
  id: number
  source_type: string
  source_key: string
  display_name: string
  added_by: string
  added_at: string
}

export interface KnowledgeSourceItem {
  id: number
  title: string
  doi: string | null
  url: string | null
  source_type: string
  topic_context: string
  status: string
  queued_at: string
  reviewed_at: string | null
  summary: string | null
}

export interface ResearchMetrics {
  approved_sources_count: number
  chat_sessions_count: number
  literature_searches_count: number
  research_hypotheses_count: number
  caveats: string[]
  [key: string]: unknown
}

export interface ResearchQuestion {
  id: number
  question: string
  status: string
  topic_context: string | null
  created_at: string | null
}

export interface Hypothesis {
  id: number
  title: string
  mechanism: string | null
  status: string
  created_at: string | null
}

export interface SqlResult {
  columns: string[]
  rows: unknown[][]
  row_count: number
}

export interface Preferences {
  agent_mode: string
  relevance_threshold: number
}
```

- [ ] **Step 2: Create `frontend/src/api/client.ts`**

```ts
import type {
  StudyNote, ChatSession, SuggestionsResponse, DatasetItem,
  LearningSourceItem, KnowledgeSourceItem, ResearchMetrics,
  ResearchQuestion, Hypothesis, SqlResult, Preferences,
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
  if (res.status === 204) return undefined as unknown as T
  return res.json() as Promise<T>
}

export const api = {
  getPreferences: () => get<Preferences>('/api/preferences'),
  setAgentMode: (mode: string) =>
    post<{ agent_mode: string }>('/api/preferences/agent-mode', { mode }),
  getSessions: () => get<ChatSession[]>('/api/sessions'),
  getStudyLog: () => get<StudyNote[]>('/api/study-log'),
  getSuggestions: () => get<SuggestionsResponse>('/api/suggestions'),
  dismissImportItem: (id: number) =>
    post<void>(`/api/suggestions/import-queue/${id}/dismiss`),
  getDatasets: (keyword?: string) =>
    get<DatasetItem[]>(keyword ? `/api/datasets?keyword=${encodeURIComponent(keyword)}` : '/api/datasets'),
  getRegistry: () => get<LearningSourceItem[]>('/api/registry'),
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
  executeSQL: (sql: string) => post<SqlResult>('/api/sql/execute', { sql }),
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/
git commit -m "feat: typed API client layer for all backend routes"
```

---

## Task 11: useChat hook

**Files:**
- Create: `frontend/src/hooks/useChat.ts`
- Create: `frontend/src/hooks/useChat.test.ts`

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/hooks/useChat.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { useChat } from './useChat'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

function makeSseResponse(events: Array<Record<string, unknown>>) {
  const lines = events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('')
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(ctrl) {
      ctrl.enqueue(encoder.encode(lines))
      ctrl.close()
    },
  })
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

describe('useChat', () => {
  beforeEach(() => { vi.restoreAllMocks() })

  it('accumulates text_delta chunks into assistant message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeSseResponse([
        { type: 'text_delta', text: 'Hello' },
        { type: 'text_delta', text: ' world' },
        { type: 'done' },
      ]),
    ))
    const { result } = renderHook(() => useChat('local_db'), { wrapper: makeWrapper() })
    await act(async () => { await result.current.sendMessage('hi') })
    expect(result.current.messages).toHaveLength(2)
    expect(result.current.messages[0]).toMatchObject({ role: 'user', content: 'hi' })
    expect(result.current.messages[1]).toMatchObject({
      role: 'assistant', content: 'Hello world', streaming: false,
    })
  })

  it('marks message as error when fetch returns non-ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response('Bad request', { status: 400 }),
    ))
    const { result } = renderHook(() => useChat('local_db'), { wrapper: makeWrapper() })
    await act(async () => { await result.current.sendMessage('hi') })
    const last = result.current.messages[result.current.messages.length - 1]
    expect(last.error).toBe(true)
    expect(last.streaming).toBe(false)
  })

  it('does not send empty messages', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useChat('local_db'), { wrapper: makeWrapper() })
    await act(async () => { await result.current.sendMessage('   ') })
    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.messages).toHaveLength(0)
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd frontend && npm test -- useChat
```
Expected: Cannot find module `./useChat`

- [ ] **Step 3: Create `frontend/src/hooks/useChat.ts`**

```ts
import { useState, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  error?: boolean
}

export function useChat(agentMode: string) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const queryClient = useQueryClient()
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return

    setMessages(prev => [
      ...prev,
      { role: 'user', content: text },
      { role: 'assistant', content: '', streaming: true },
    ])
    setIsStreaming(true)
    abortRef.current = new AbortController()

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, agent_mode: agentMode, history: [] }),
        signal: abortRef.current.signal,
      })

      if (!res.ok) {
        throw new Error(await res.text() || `${res.status}`)
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (!payload) continue
          try {
            const event = JSON.parse(payload) as { type: string; text?: string }
            if (event.type === 'text_delta') {
              setMessages(prev => {
                const next = [...prev]
                const last = { ...next[next.length - 1] }
                last.content = (last.content ?? '') + (event.text ?? '')
                next[next.length - 1] = last
                return next
              })
            } else if (event.type === 'done') {
              setMessages(prev => {
                const next = [...prev]
                next[next.length - 1] = { ...next[next.length - 1], streaming: false }
                return next
              })
              queryClient.invalidateQueries({ queryKey: ['sessions'] })
            }
          } catch {
            // skip malformed SSE line
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      setMessages(prev => {
        const next = [...prev]
        next[next.length - 1] = {
          ...next[next.length - 1],
          content: err instanceof Error ? err.message : 'Unknown error',
          streaming: false,
          error: true,
        }
        return next
      })
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [agentMode, isStreaming, queryClient])

  return { messages, isStreaming, sendMessage }
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd frontend && npm test -- useChat
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/
git commit -m "feat: useChat hook for SSE streaming"
```

---

## Task 12: App layout, Sidebar, PanelNav, ChatPanel, MessageBubble

**Files:**
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/PanelNav.tsx`
- Create: `frontend/src/components/ChatPanel.tsx`
- Create: `frontend/src/components/MessageBubble.tsx`
- Modify: `frontend/src/main.tsx` (replace placeholder)

- [ ] **Step 1: Create `frontend/src/components/MessageBubble.tsx`**

```tsx
import type { Message } from '../hooks/useChat'

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <div style={{
      marginBottom: 8,
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
    }}>
      <div style={{
        maxWidth: '80%',
        padding: '6px 12px',
        borderRadius: 8,
        background: isUser ? '#1e3a8a' : message.error ? '#fee2e2' : '#f1f5f9',
        color: isUser ? '#fff' : message.error ? '#dc2626' : '#0f172a',
        fontSize: 13,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {message.content}
        {message.streaming && <span style={{ opacity: 0.5 }}>▋</span>}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `frontend/src/components/ChatPanel.tsx`**

```tsx
import { useState, useRef, useEffect } from 'react'
import { useChat } from '../hooks/useChat'
import MessageBubble from './MessageBubble'

export default function ChatPanel({ agentMode }: { agentMode: string }) {
  const { messages, isStreaming, sendMessage } = useChat(agentMode)
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return
    sendMessage(input)
    setInput('')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 12 }}>
      <h3 style={{ margin: '0 0 8px', fontSize: 15, color: '#0f172a' }}>
        Chat <span style={{ fontSize: 12, color: '#64748b', fontWeight: 400 }}>({agentMode})</span>
      </h3>
      <div style={{ flex: 1, overflowY: 'auto', marginBottom: 8 }}>
        {messages.length === 0 && (
          <p style={{ color: '#94a3b8', fontSize: 13, textAlign: 'center', marginTop: 32 }}>
            Start a conversation…
          </p>
        )}
        {messages.map((msg, i) => <MessageBubble key={i} message={msg} />)}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={isStreaming}
          style={{
            flex: 1, padding: '8px 10px', border: '1px solid #cbd5e1',
            borderRadius: 6, fontSize: 13,
          }}
        />
        <button
          type="submit"
          disabled={isStreaming || !input.trim()}
          style={{
            padding: '8px 14px', background: '#1e3a8a', color: '#fff',
            border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13,
          }}
        >
          Send
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/components/PanelNav.tsx`**

```tsx
import { NavLink } from 'react-router-dom'

const PANELS = [
  { path: '/suggestions', label: 'Suggestions' },
  { path: '/study-log', label: 'Study Log' },
  { path: '/datasets', label: 'Datasets' },
  { path: '/registry', label: 'Registry' },
  { path: '/knowledge-library', label: 'Knowledge Library' },
  { path: '/research', label: 'Research' },
  { path: '/sql', label: 'SQL' },
]

export default function PanelNav() {
  return (
    <nav style={{
      display: 'flex', borderBottom: '1px solid #e2e8f0',
      overflowX: 'auto', flexShrink: 0, background: '#f8fafc',
    }}>
      {PANELS.map(p => (
        <NavLink
          key={p.path}
          to={p.path}
          style={({ isActive }) => ({
            padding: '8px 12px',
            textDecoration: 'none',
            fontSize: 12,
            fontWeight: isActive ? 700 : 400,
            color: isActive ? '#1e3a8a' : '#475569',
            borderBottom: isActive ? '2px solid #1e3a8a' : '2px solid transparent',
            whiteSpace: 'nowrap',
            flexShrink: 0,
          })}
        >
          {p.label}
        </NavLink>
      ))}
    </nav>
  )
}
```

- [ ] **Step 4: Create `frontend/src/components/Sidebar.tsx`**

```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

const MODES = [
  { value: 'local_db', label: 'Local DB' },
  { value: 'external_db', label: 'External DB' },
  { value: 'neuro_tutor', label: 'Neuro Tutor' },
  { value: 'neuro_research', label: 'Neuro Research' },
]

export default function Sidebar({ agentMode }: { agentMode: string }) {
  const queryClient = useQueryClient()
  const { data: sessions = [] } = useQuery({
    queryKey: ['sessions'],
    queryFn: api.getSessions,
  })

  const setMode = useMutation({
    mutationFn: (mode: string) => api.setAgentMode(mode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['preferences'] }),
  })

  return (
    <div style={{
      width: 180, flexShrink: 0, borderRight: '1px solid #e2e8f0',
      padding: 12, overflowY: 'auto', background: '#f8fafc',
    }}>
      <div>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', marginBottom: 4 }}>
          AGENT MODE
        </div>
        <select
          value={agentMode}
          onChange={e => setMode.mutate(e.target.value)}
          style={{ width: '100%', padding: '4px 6px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 4 }}
        >
          {MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
      </div>
      <div style={{ marginTop: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', marginBottom: 4 }}>
          PREVIOUS SESSIONS
        </div>
        {sessions.length === 0 ? (
          <div style={{ fontSize: 11, color: '#94a3b8' }}>No sessions yet</div>
        ) : (
          sessions.map(s => (
            <div key={s.id} style={{
              padding: '4px 0', borderBottom: '1px solid #e2e8f0', cursor: 'default',
            }}>
              <div style={{ fontSize: 11, color: '#0f172a', lineHeight: 1.3 }}>
                {s.inferred_topic}
              </div>
              <div style={{ fontSize: 10, color: '#94a3b8' }}>
                {s.started_at.slice(0, 10)} · {s.message_count} msgs
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Create `frontend/src/App.tsx`**

```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import PanelNav from './components/PanelNav'
import SuggestionsPanel from './pages/SuggestionsPanel'
import StudyLogPanel from './pages/StudyLogPanel'
import DatasetsPanel from './pages/DatasetsPanel'
import RegistryPanel from './pages/RegistryPanel'
import KnowledgeLibraryPanel from './pages/KnowledgeLibraryPanel'
import ResearchPanel from './pages/ResearchPanel'
import SqlPanel from './pages/SqlPanel'

export default function App() {
  const { data: prefs } = useQuery({
    queryKey: ['preferences'],
    queryFn: api.getPreferences,
  })
  const agentMode = prefs?.agent_mode ?? 'local_db'

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar agentMode={agentMode} />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ flex: '0 0 55%', overflow: 'hidden', borderRight: '1px solid #e2e8f0' }}>
          <ChatPanel agentMode={agentMode} />
        </div>
        <div style={{ flex: '0 0 45%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <PanelNav />
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <Routes>
              <Route path="/suggestions" element={<SuggestionsPanel />} />
              <Route path="/study-log" element={<StudyLogPanel />} />
              <Route path="/datasets" element={<DatasetsPanel />} />
              <Route path="/registry" element={<RegistryPanel />} />
              <Route path="/knowledge-library" element={<KnowledgeLibraryPanel />} />
              <Route path="/research" element={<ResearchPanel />} />
              <Route path="/sql" element={<SqlPanel />} />
              <Route path="*" element={<Navigate to="/suggestions" replace />} />
            </Routes>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Update `frontend/src/main.tsx`**

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import App from './App'

const queryClient = new QueryClient()
const router = createBrowserRouter([{ path: '/*', element: <App /> }])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
)
```

- [ ] **Step 7: Create stub panel pages so App.tsx compiles**

Create each of these files with a minimal stub (full implementation in Tasks 13–19):

```tsx
// frontend/src/pages/SuggestionsPanel.tsx
export default function SuggestionsPanel() { return <div style={{padding:12}}>Suggestions</div> }
```

Repeat for `StudyLogPanel.tsx`, `DatasetsPanel.tsx`, `RegistryPanel.tsx`, `KnowledgeLibraryPanel.tsx`, `ResearchPanel.tsx`, `SqlPanel.tsx` — same stub pattern with the panel name as text content.

- [ ] **Step 8: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 9: Verify dev server loads app**

Start the FastAPI server first:
```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
```
Then in a second terminal:
```bash
cd frontend && npm run dev
```
Open `http://localhost:5173/` — the two-column layout should render with sidebar, chat panel, and panel nav tabs. The `/api/preferences` call should return data (check browser Network tab). Stop both servers.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/
git commit -m "feat: App layout, Sidebar, PanelNav, ChatPanel, MessageBubble"
```

---

## Task 13: SuggestionsPanel

**Files:**
- Modify: `frontend/src/pages/SuggestionsPanel.tsx` (replace stub)
- Create: `frontend/src/pages/SuggestionsPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/pages/SuggestionsPanel.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import SuggestionsPanel from './SuggestionsPanel'

function makeWrapper(data: unknown) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  qc.setQueryData(['suggestions'], data)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('SuggestionsPanel', () => {
  it('shows empty state when no suggestions', () => {
    render(<SuggestionsPanel />, { wrapper: makeWrapper({ import_queue: [], source_suggestions: [] }) })
    expect(screen.getByText(/No pending import suggestions/)).toBeTruthy()
  })

  it('renders import queue items', () => {
    render(<SuggestionsPanel />, {
      wrapper: makeWrapper({
        import_queue: [{ id: 1, source: 'openneuro', source_id: 'ds001', title: 'Test DS',
          status: 'pending', suggested_at: '2026-01-01', reason: null, chapter_ref: null }],
        source_suggestions: [],
      }),
    })
    expect(screen.getByText(/Test DS/)).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd frontend && npm test -- SuggestionsPanel
```
Expected: the test can't find rendered text because stub renders "Suggestions"

- [ ] **Step 3: Replace stub with full implementation**

```tsx
// frontend/src/pages/SuggestionsPanel.tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export default function SuggestionsPanel() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['suggestions'],
    queryFn: api.getSuggestions,
  })
  const dismiss = useMutation({
    mutationFn: (id: number) => api.dismissImportItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['suggestions'] }),
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading…</div>
  if (isError) return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>

  const { import_queue, source_suggestions } = data!
  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Dataset Import Requests</h4>
      {import_queue.length === 0
        ? <p style={{ color: '#94a3b8', fontSize: 13 }}>No pending import suggestions.</p>
        : import_queue.map(item => (
            <div key={item.id} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}>
              <strong>{item.title ?? item.source_id}</strong>
              {' — '}<code style={{ fontSize: 11 }}>{item.source}:{item.source_id}</code>
              {item.chapter_ref && <div style={{ fontSize: 12, color: '#64748b' }}>While reading: {item.chapter_ref}</div>}
              {item.reason && <p style={{ fontSize: 12, margin: '4px 0', color: '#475569' }}>{item.reason}</p>}
              <button
                onClick={() => dismiss.mutate(item.id)}
                style={{ fontSize: 12, marginTop: 6, padding: '3px 10px', cursor: 'pointer' }}
              >
                Dismiss
              </button>
            </div>
          ))}
      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />
      <h4 style={{ marginBottom: 8 }}>Connector Requests</h4>
      {source_suggestions.length === 0
        ? <p style={{ color: '#94a3b8', fontSize: 13 }}>No pending source suggestions.</p>
        : source_suggestions.map(item => (
            <div key={item.id} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}>
              <strong>{item.display_name ?? item.reference ?? '—'}</strong>
              {' '}<code style={{ fontSize: 11 }}>({item.suggestion_type})</code>
              {item.reason && <p style={{ fontSize: 12, margin: '4px 0', color: '#475569' }}>{item.reason}</p>}
            </div>
          ))}
    </div>
  )
}
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd frontend && npm test -- SuggestionsPanel
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SuggestionsPanel.tsx frontend/src/pages/SuggestionsPanel.test.tsx
git commit -m "feat: SuggestionsPanel"
```

---

## Task 14: StudyLogPanel

**Files:**
- Modify: `frontend/src/pages/StudyLogPanel.tsx`

- [ ] **Step 1: Replace stub with implementation**

```tsx
// frontend/src/pages/StudyLogPanel.tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export default function StudyLogPanel() {
  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['study-log'],
    queryFn: api.getStudyLog,
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading…</div>
  if (isError) return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Study Tags ({data.length})</h4>
      {data.length === 0
        ? <p style={{ color: '#94a3b8', fontSize: 13 }}>No study tags yet.</p>
        : (
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
                  <td style={{ padding: '4px 8px', color: '#94a3b8' }}>{row.section_ref ?? '—'}</td>
                  <td style={{ padding: '4px 8px', color: '#94a3b8' }}>{row.tagged_at.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/StudyLogPanel.tsx
git commit -m "feat: StudyLogPanel"
```

---

## Task 15: DatasetsPanel

**Files:**
- Modify: `frontend/src/pages/DatasetsPanel.tsx`

- [ ] **Step 1: Replace stub with implementation**

```tsx
// frontend/src/pages/DatasetsPanel.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export default function DatasetsPanel() {
  const [keyword, setKeyword] = useState('')
  const [submitted, setSubmitted] = useState<string | undefined>(undefined)

  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['datasets', submitted],
    queryFn: () => api.getDatasets(submitted),
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitted(keyword.trim() || undefined)
  }

  if (isLoading) return <div style={{ padding: 12 }}>Loading…</div>
  if (isError) return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Datasets</h4>
      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          placeholder="Search by source ID…"
          style={{ flex: 1, padding: '5px 8px', border: '1px solid #cbd5e1', borderRadius: 4, fontSize: 12 }}
        />
        <button type="submit" style={{ padding: '5px 12px', fontSize: 12, cursor: 'pointer' }}>
          Search
        </button>
      </form>
      {data.length === 0
        ? <p style={{ color: '#94a3b8', fontSize: 13 }}>No datasets found.</p>
        : (
          <>
            <p style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}>{data.length} dataset(s)</p>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                  <th style={{ padding: '4px 8px' }}>Source</th>
                  <th style={{ padding: '4px 8px' }}>ID</th>
                </tr>
              </thead>
              <tbody>
                {data.map(row => (
                  <tr key={row.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '4px 8px', color: '#475569' }}>{row.source}</td>
                    <td style={{ padding: '4px 8px' }}>{row.source_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/DatasetsPanel.tsx
git commit -m "feat: DatasetsPanel"
```

---

## Task 16: RegistryPanel

**Files:**
- Modify: `frontend/src/pages/RegistryPanel.tsx`

- [ ] **Step 1: Replace stub with implementation**

```tsx
// frontend/src/pages/RegistryPanel.tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { LearningSourceItem } from '../api/types'

function SourceGroup({ title, items }: { title: string; items: LearningSourceItem[] }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{title} ({items.length})</div>
      {items.length === 0
        ? <p style={{ color: '#94a3b8', fontSize: 12 }}>None yet.</p>
        : items.map(item => (
            <div key={item.id} style={{ padding: '6px 8px', border: '1px solid #e2e8f0', borderRadius: 6, marginBottom: 4 }}>
              <div style={{ fontSize: 13 }}>{item.display_name}</div>
              <div style={{ fontSize: 11, color: '#64748b' }}>
                {item.source_key} · added by {item.added_by} on {item.added_at.slice(0, 10)}
              </div>
            </div>
          ))}
    </div>
  )
}

export default function RegistryPanel() {
  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['registry'],
    queryFn: api.getRegistry,
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading…</div>
  if (isError) return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>

  const books = data.filter(r => r.source_type === 'book')
  const papers = data.filter(r => r.source_type === 'paper')
  const datasets = data.filter(r => r.source_type === 'dataset')
  const other = data.filter(r => !['book', 'paper', 'dataset'].includes(r.source_type))

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 12 }}>Learning Registry</h4>
      <SourceGroup title="Books" items={books} />
      <SourceGroup title="Papers & Studies" items={papers} />
      <SourceGroup title="Datasets" items={datasets} />
      {other.length > 0 && <SourceGroup title="Other" items={other} />}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend && npx tsc --noEmit && git add frontend/src/pages/RegistryPanel.tsx && git commit -m "feat: RegistryPanel"
```

---

## Task 17: KnowledgeLibraryPanel

**Files:**
- Modify: `frontend/src/pages/KnowledgeLibraryPanel.tsx`
- Create: `frontend/src/pages/KnowledgeLibraryPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/pages/KnowledgeLibraryPanel.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import KnowledgeLibraryPanel from './KnowledgeLibraryPanel'

function makeWrapper(data: unknown) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  qc.setQueryData(['knowledge-library', 'all'], data)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('KnowledgeLibraryPanel', () => {
  it('shows empty state', () => {
    render(<KnowledgeLibraryPanel />, { wrapper: makeWrapper([]) })
    expect(screen.getByText(/No sources/)).toBeTruthy()
  })

  it('renders pending source with approve and reject buttons', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 1, title: 'LTP Review', doi: null, url: null,
        source_type: 'paper', topic_context: 'plasticity',
        status: 'pending', queued_at: '2026-01-01', reviewed_at: null, summary: null,
      }]),
    })
    expect(screen.getByText('LTP Review')).toBeTruthy()
    expect(screen.getByText('Approve')).toBeTruthy()
    expect(screen.getByText('Reject')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd frontend && npm test -- KnowledgeLibraryPanel
```
Expected: test fails (stub renders "Knowledge Library")

- [ ] **Step 3: Replace stub with full implementation**

```tsx
// frontend/src/pages/KnowledgeLibraryPanel.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export default function KnowledgeLibraryPanel() {
  const [statusFilter, setStatusFilter] = useState('all')
  const queryClient = useQueryClient()

  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['knowledge-library', statusFilter],
    queryFn: () => api.getKnowledgeLibrary(statusFilter),
  })

  const approve = useMutation({
    mutationFn: (id: number) => api.approveSource(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge-library'] }),
  })
  const reject = useMutation({
    mutationFn: (id: number) => api.rejectSource(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge-library'] }),
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading…</div>
  if (isError) return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <h4>Knowledge Library</h4>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={{ fontSize: 12, padding: '3px 6px', border: '1px solid #cbd5e1', borderRadius: 4 }}
        >
          <option value="all">All</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>
      {data.length === 0
        ? <p style={{ color: '#94a3b8', fontSize: 13 }}>No sources matching filter.</p>
        : data.map(item => (
            <div key={item.id} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{item.title}</div>
              <div style={{ fontSize: 11, color: '#64748b', margin: '2px 0' }}>
                {item.source_type} · {item.topic_context.slice(0, 80)}
              </div>
              {item.doi && <div style={{ fontSize: 11 }}>DOI: {item.doi}</div>}
              {item.summary && (
                <details style={{ fontSize: 12, marginTop: 4 }}>
                  <summary style={{ cursor: 'pointer', color: '#475569' }}>Summary</summary>
                  <p style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{item.summary}</p>
                </details>
              )}
              {item.status === 'pending' && (
                <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                  <button
                    onClick={() => approve.mutate(item.id)}
                    disabled={approve.isPending}
                    style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer', background: '#1e3a8a', color: '#fff', border: 'none', borderRadius: 4 }}
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => reject.mutate(item.id)}
                    disabled={reject.isPending}
                    style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
                  >
                    Reject
                  </button>
                </div>
              )}
              {item.status !== 'pending' && (
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                  {item.status} · {item.reviewed_at?.slice(0, 10) ?? ''}
                </div>
              )}
            </div>
          ))}
    </div>
  )
}
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd frontend && npm test -- KnowledgeLibraryPanel
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/KnowledgeLibraryPanel.tsx frontend/src/pages/KnowledgeLibraryPanel.test.tsx
git commit -m "feat: KnowledgeLibraryPanel with approve/reject"
```

---

## Task 18: ResearchPanel and SqlPanel

**Files:**
- Modify: `frontend/src/pages/ResearchPanel.tsx`
- Modify: `frontend/src/pages/SqlPanel.tsx`

- [ ] **Step 1: Replace ResearchPanel stub**

```tsx
// frontend/src/pages/ResearchPanel.tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export default function ResearchPanel() {
  const queryClient = useQueryClient()

  const { data: metrics, isLoading: mLoading } = useQuery({
    queryKey: ['research-metrics'],
    queryFn: api.getResearchMetrics,
  })
  const { data: questions = [], isLoading: qLoading } = useQuery({
    queryKey: ['research-questions'],
    queryFn: () => api.getResearchQuestions('all'),
  })
  const { data: hypotheses = [], isLoading: hLoading } = useQuery({
    queryKey: ['research-hypotheses'],
    queryFn: () => api.getHypotheses('all'),
  })

  const snapshot = useMutation({
    mutationFn: () => fetch('/api/research/metrics/snapshot', { method: 'POST' }).then(r => r.json()),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-metrics'] }),
  })

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Research</h4>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>Metrics</div>
        {mLoading ? <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading…</span> : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            {([
              ['Approved Sources', metrics?.approved_sources_count],
              ['Sessions', metrics?.chat_sessions_count],
              ['Lit Searches', metrics?.literature_searches_count],
              ['Hypotheses', metrics?.research_hypotheses_count],
            ] as [string, number | undefined][]).map(([label, val]) => (
              <div key={label} style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: '6px 10px' }}>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{val ?? '—'}</div>
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
        {qLoading ? <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading…</span> : (
          questions.length === 0
            ? <p style={{ color: '#94a3b8', fontSize: 12 }}>No research questions yet.</p>
            : questions.map(q => (
                <div key={q.id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9' }}>
                  <div style={{ fontSize: 13 }}>{q.question}</div>
                  <div style={{ fontSize: 11, color: '#94a3b8' }}>{q.status} · {q.created_at?.slice(0, 10)}</div>
                </div>
              ))
        )}
      </div>

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <div>
        <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>
          Draft Hypotheses ({hypotheses.length})
        </div>
        {hLoading ? <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading…</span> : (
          hypotheses.length === 0
            ? <p style={{ color: '#94a3b8', fontSize: 12 }}>No hypotheses yet.</p>
            : hypotheses.map(h => (
                <div key={h.id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9' }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{h.title}</div>
                  <div style={{ fontSize: 11, color: '#94a3b8' }}>{h.status} · {h.created_at?.slice(0, 10)}</div>
                </div>
              ))
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Replace SqlPanel stub**

```tsx
// frontend/src/pages/SqlPanel.tsx
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import type { SqlResult } from '../api/types'

const DEFAULT_SQL = 'SELECT * FROM ingest_runs LIMIT 10;'

export default function SqlPanel() {
  const [sql, setSql] = useState(DEFAULT_SQL)
  const [result, setResult] = useState<SqlResult | null>(null)
  const [execError, setExecError] = useState<string | null>(null)

  const execute = useMutation({
    mutationFn: () => api.executeSQL(sql),
    onSuccess: (data) => { setResult(data); setExecError(null) },
    onError: (err: Error) => {
      setExecError(err.message)
      setResult(null)
    },
  })

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>SQL Query</h4>
      <textarea
        value={sql}
        onChange={e => setSql(e.target.value)}
        rows={5}
        style={{ width: '100%', fontFamily: 'monospace', fontSize: 12, padding: 8,
          border: '1px solid #cbd5e1', borderRadius: 4, resize: 'vertical' }}
      />
      <button
        onClick={() => execute.mutate()}
        disabled={execute.isPending || !sql.trim()}
        style={{ marginTop: 6, padding: '5px 14px', fontSize: 12, cursor: 'pointer',
          background: '#1e3a8a', color: '#fff', border: 'none', borderRadius: 4 }}
      >
        {execute.isPending ? 'Running…' : 'Run Query'}
      </button>

      {execError && (
        <div style={{ marginTop: 8, padding: 8, background: '#fee2e2', borderRadius: 4, fontSize: 12, color: '#dc2626' }}>
          {execError}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{result.row_count} row(s)</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0', background: '#f8fafc' }}>
                  {result.columns.map(col => (
                    <th key={col} style={{ padding: '4px 8px', textAlign: 'left', whiteSpace: 'nowrap' }}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    {row.map((cell, j) => (
                      <td key={j} style={{ padding: '4px 8px', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {cell === null ? <span style={{ color: '#94a3b8' }}>null</span> : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ResearchPanel.tsx frontend/src/pages/SqlPanel.tsx
git commit -m "feat: ResearchPanel and SqlPanel"
```

---

## Task 19: Full integration check and manual test plan

**Files:**
- Create: `docs/testsPlans/manualTestPlan_ui2_react_workbench.md`
- Modify: `docs/projectStatus.md` (add active test plan)

- [ ] **Step 1: Run full Python test suite**

```bash
uv run pytest tests/ -q
```
Expected: all existing tests pass with no new failures

- [ ] **Step 2: Run frontend Vitest suite**

```bash
cd frontend && npm test
```
Expected: all Vitest tests pass (useChat × 3, SuggestionsPanel × 2, KnowledgeLibraryPanel × 2 = 7 minimum)

- [ ] **Step 3: Verify TypeScript compiles cleanly**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 4: Create manual test plan**

```markdown
# Manual Test Plan — UI-2 React Workbench

**Phase:** UI-2
**Status:** In progress
**Last updated:** 2026-05-11

## Prerequisites

1. Run automated tests — no new failures:
   ```bash
   uv run pytest tests/ -q
   ```
   Pass criteria: all existing tests pass; failure count matches `docs/testLog.md` open items only.

2. Run frontend Vitest:
   ```bash
   cd frontend && npm test
   ```
   Pass criteria: all tests pass.

## Setup for T2–T10

**Terminal 1 — FastAPI:**
```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
```
Expected: `Application startup complete.`

**Terminal 2 — Vite:**
```bash
cd frontend && npm run dev
```
Expected: `Local: http://localhost:5173/`

Keep both running for T2–T10. Open `http://localhost:5173/` in the browser.

---

## T1 — Automated test prerequisite

Run `uv run pytest tests/ -q`. Verify no new failures.

**Pass:** test count is ≥ 436 with no new failures.

---

## T2 — App loads and proxies to backend

Open `http://localhost:5173/`. The two-column layout should render: narrow sidebar on the left, chat panel centre-left, panel nav + panel area right. The sidebar should show "Agent Mode" dropdown.

Open browser DevTools → Network. Confirm `GET /api/preferences` returns 200 with JSON containing `agent_mode`.

**Pass:** layout renders, `/api/preferences` returns 200.

---

## T3 — Chat streams a response

In the chat panel, type "What is LTP?" and press Send. The assistant message should appear and stream text in real time. After streaming ends the cursor disappears.

**Pass:** assistant response streams and completes without error.

---

## T4 — Suggestions panel

Click the "Suggestions" tab. The panel should load without error (empty state or items from the DB).

**Pass:** panel renders, no JS console errors.

---

## T5 — Study Log panel

Click "Study Log". The panel should show a table of study tags or the empty state message.

**Pass:** panel renders, no JS console errors.

---

## T6 — Datasets panel

Click "Datasets". The panel should show the dataset list or empty state. Type a source ID fragment in the search box and click Search.

**Pass:** panel renders, search does not crash.

---

## T7 — Registry panel

Click "Registry". Books, Papers & Studies, and Datasets sections should render (each empty or with data).

**Pass:** panel renders, no JS console errors.

---

## T8 — Knowledge Library panel

Click "Knowledge Library". Change the status dropdown to "Pending". If pending sources exist, Approve and Reject buttons should appear. Click Approve on one — the list should refresh and the item should move to approved.

**Pass:** panel renders, filter works, approve/reject refreshes list.

---

## T9 — Research panel

Click "Research". The four metric tiles should show counts. Click "Snapshot Metrics" — a new snapshot is saved (no error).

**Pass:** metrics render, snapshot fires without error.

---

## T10 — SQL panel

Click "SQL". The default query `SELECT * FROM ingest_runs LIMIT 10;` should be pre-filled. Click "Run Query". Results table renders (columns + rows or empty).

Change the SQL to `NOT VALID!!!` and run. An error message should appear in red below the button.

**Pass:** valid query returns result table; invalid query shows error message.
```

Save to `docs/testsPlans/manualTestPlan_ui2_react_workbench.md`.

- [ ] **Step 5: Update `docs/projectStatus.md`**

In the UI epoch row, change Next from `UI-2: React workbench prototype` to `UI-2: in progress`.
Add to Active test plan: `docs/testsPlans/manualTestPlan_ui2_react_workbench.md`.

- [ ] **Step 6: Commit**

```bash
git add docs/testsPlans/manualTestPlan_ui2_react_workbench.md docs/projectStatus.md
git commit -m "docs: UI-2 manual test plan; mark phase in progress"
```
