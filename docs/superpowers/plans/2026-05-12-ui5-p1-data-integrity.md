# UI-5 P1: Data Integrity Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix six silent data-integrity gaps between React and Streamlit so that study tags are embedded, approved sources are indexed in ChromaDB, imported dataset queue items are marked resolved, promote creates properly-attributed registry entries, and the registry add form persists structured topic data.

**Architecture:** Four backend route fixes (embed after tag create, index after approve, update queue on import, harden promote provenance), one backend request-model change (registry topics/added_by), one frontend condition (promote gating), one frontend form change (registry topics field), and a warning-propagation pattern on the two operations that call vector stores.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, ChromaDB, React 18, TanStack Query v5, Vitest + React Testing Library.

---

## File Map

| Change | File |
|---|---|
| Modify | `src/neurodb/api/deps.py` |
| Modify | `src/neurodb/api/schemas/study_log.py` |
| Modify | `src/neurodb/api/schemas/knowledge_library.py` |
| Modify | `src/neurodb/api/routes/study_log.py` |
| Modify | `src/neurodb/api/routes/knowledge_library.py` |
| Modify | `src/neurodb/api/routes/datasets.py` |
| Modify | `src/neurodb/api/routes/suggestions.py` |
| Modify | `src/neurodb/api/routes/registry.py` |
| Modify | `frontend/src/api/types.ts` |
| Modify | `frontend/src/pages/StudyLogPanel.tsx` |
| Modify | `frontend/src/pages/KnowledgeLibraryPanel.tsx` |
| Modify | `frontend/src/pages/SuggestionsPanel.tsx` |
| Modify | `frontend/src/pages/RegistryPanel.tsx` |
| Modify | `tests/unit/test_api_study_log.py` |
| Modify | `tests/unit/test_api_knowledge_library.py` |
| Modify | `tests/unit/test_api_datasets_import.py` |
| Modify | `tests/unit/test_api_suggestions.py` |
| Modify | `tests/unit/test_api_registry.py` |
| Modify | `frontend/src/pages/StudyLogPanel.test.tsx` |
| Modify | `frontend/src/pages/KnowledgeLibraryPanel.test.tsx` |
| Modify | `frontend/src/pages/SuggestionsPanel.test.tsx` |
| Modify | `frontend/src/pages/RegistryPanel.test.tsx` |

---

## Task 1: Add `get_vector_store` and `get_knowledge_store` deps

**Files:**
- Modify: `src/neurodb/api/deps.py`

Context: Route handlers use dependency injection via `Depends(get_engine)`. Two new helpers follow the same pattern — returning named objects from `app.state`. These are used by Tasks 2 and 3.

- [ ] **Step 1: Write the full updated `deps.py`**

Replace the entire file contents:

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


def get_vector_store(request: Request):
    return request.app.state.vector_store


def get_knowledge_store(request: Request):
    return request.app.state.knowledge_store


def get_research_stores(request: Request) -> dict:
    return {
        "vector_store": request.app.state.vector_store,
        "knowledge_store": request.app.state.knowledge_store,
        "context_store": request.app.state.context_store,
    }


def get_task_store(request: Request) -> dict:
    return request.app.state.tasks
```

- [ ] **Step 2: Run existing tests to verify no regression**

```bash
uv run pytest tests/unit/test_api_study_log.py tests/unit/test_api_knowledge_library.py -q
```

Expected: all existing tests pass (they don't exercise the new deps yet).

- [ ] **Step 3: Commit**

```bash
git add src/neurodb/api/deps.py
git commit -m "feat: add get_vector_store and get_knowledge_store deps"
```

---

## Task 2: P1.1 — Study log vector embedding

**Files:**
- Modify: `src/neurodb/api/schemas/study_log.py`
- Modify: `src/neurodb/api/routes/study_log.py`
- Modify: `tests/unit/test_api_study_log.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/pages/StudyLogPanel.tsx`
- Modify: `frontend/src/pages/StudyLogPanel.test.tsx`

Context: `POST /api/study-log` creates the DB row but never calls `embed_note`. The route needs `get_vector_store` dependency (added in Task 1) and must call `embed_note` after a successful DB write. If the call fails, the route returns `warnings: [...]` instead of raising. `StudyNoteItem` needs the `warnings` field; the React component shows it inline.

- [ ] **Step 1: Add `warnings` field to `StudyNoteItem` schema**

Replace `src/neurodb/api/schemas/study_log.py`:

```python
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
    warnings: list[str] = []
```

- [ ] **Step 2: Write failing Python tests**

Add to `tests/unit/test_api_study_log.py`. First update `_make_app` to set `app.state.vector_store`, then add two new tests at the bottom of the file:

```python
from unittest.mock import MagicMock

# Replace the existing _make_app and _make_client with this version:
def _make_app(engine, vector_store=None):
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = vector_store if vector_store is not None else MagicMock()
    app.include_router(router, prefix="/api")
    return app


def _make_client(vector_store=None):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine, vector_store)), engine
```

Then add these two tests at the end of the file:

```python
def test_post_study_log_calls_embed_note():
    mock_vs = MagicMock()
    client, engine = _make_client(mock_vs)
    _insert_dataset(engine, "openneuro", "ds001")

    resp = client.post("/api/study-log", json={
        "source": "openneuro",
        "source_id": "ds001",
        "concept_tag": "LTP",
        "section_ref": "Ch3",
        "note_text": "Notes here",
    })

    assert resp.status_code == 200
    assert resp.json()["warnings"] == []
    mock_vs.upsert_note.assert_called_once()


def test_post_study_log_returns_warning_when_embed_fails():
    mock_vs = MagicMock()
    mock_vs.upsert_note.side_effect = RuntimeError("chroma down")
    client, engine = _make_client(mock_vs)
    _insert_dataset(engine, "openneuro", "ds001")

    resp = client.post("/api/study-log", json={
        "source": "openneuro",
        "source_id": "ds001",
        "concept_tag": "LTP",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["warnings"]) == 1
    assert "Vector embedding failed" in data["warnings"][0]
```

- [ ] **Step 3: Run new tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_study_log.py::test_post_study_log_calls_embed_note tests/unit/test_api_study_log.py::test_post_study_log_returns_warning_when_embed_fails -v
```

Expected: FAIL — route doesn't call embed_note yet.

- [ ] **Step 4: Implement the route change**

Replace the entire `src/neurodb/api/routes/study_log.py`:

```python
"""GET and POST /api/study-log routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine

from neurodb.api.deps import get_engine, get_vector_store
from neurodb.api.schemas.study_log import StudyNoteItem
from neurodb.db import get_session
from neurodb.embed_hooks import embed_note
from neurodb.study import list_tags, tag_dataset

logger = logging.getLogger(__name__)

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
    vector_store=Depends(get_vector_store),
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
        item = StudyNoteItem(
            id=note.id,
            source=body.source,
            source_id=body.source_id,
            concept_tag=note.concept_tag,
            section_ref=note.section_ref,
            note_text=note.note_text,
            tagged_at=note.tagged_at,
        )
        note_id = note.id  # capture before session closes — attributes expire on commit
    warnings: list[str] = []
    try:
        embed_note(
            vector_store, note_id, body.source, body.source_id,
            body.concept_tag, body.section_ref, body.note_text,
        )
    except Exception as exc:
        logger.exception("embed_note failed for note %d", note_id)
        warnings.append(f"Vector embedding failed: {exc}")
    return item.model_copy(update={"warnings": warnings})
```

- [ ] **Step 5: Run all study log tests**

```bash
uv run pytest tests/unit/test_api_study_log.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Add `warnings` to `StudyNote` in `frontend/src/api/types.ts`**

In `types.ts`, update the `StudyNote` interface:

```ts
export interface StudyNote {
  id: number
  source: string
  source_id: string
  concept_tag: string
  section_ref: string | null
  note_text: string | null
  tagged_at: string
  warnings?: string[]
}
```

- [ ] **Step 7: Write failing frontend test for warning banner**

Add to `frontend/src/pages/StudyLogPanel.test.tsx` (after the existing imports — add `waitFor` if not already imported):

```tsx
  it('shows warning banner when create returns a warning', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/study-log' && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 1,
            source: 'openneuro',
            source_id: 'ds001',
            concept_tag: 'LTP',
            section_ref: null,
            note_text: null,
            tagged_at: '2026-01-01T00:00:00',
            warnings: ['Vector embedding failed: chroma down'],
          }),
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<StudyLogPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Tag'))
    fireEvent.change(screen.getByPlaceholderText('source_id'), { target: { value: 'ds001' } })
    fireEvent.change(screen.getByPlaceholderText('concept_tag'), { target: { value: 'LTP' } })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(screen.getByText(/Vector embedding failed/)).toBeTruthy()
    })
  })
```

- [ ] **Step 8: Run frontend test to confirm it fails**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A3 "warning banner"
```

Expected: test fails — warning banner not rendered yet.

- [ ] **Step 9: Implement warning banner in `StudyLogPanel.tsx`**

In `StudyTagsView`, add a `warning` state and populate it in the mutation's `onSuccess`. Add the `useEffect` is not needed — just local state.

In `StudyTagsView` inside `frontend/src/pages/StudyLogPanel.tsx`, add after the existing `formError` state line:

```tsx
const [warning, setWarning] = useState<string | null>(null)
```

Update the `create` mutation `onSuccess`:

```tsx
  const create = useMutation({
    mutationFn: (body: CreateStudyNoteRequest) => api.createStudyNote(body),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['study-log'] })
      setShowForm(false)
      setForm({ source: 'openneuro', source_id: '', concept_tag: '', section_ref: '', note_text: '' })
      setFormError(null)
      setWarning(data.warnings?.length ? data.warnings[0] : null)
    },
  })
```

Add the warning banner after the Add Tag button in the JSX (after the `</form>` closing tag, before the end of the component return):

```tsx
      {warning && (
        <div style={{
          color: '#92400e',
          background: '#fef3c7',
          padding: '4px 8px',
          borderRadius: 4,
          fontSize: 11,
          marginTop: 4,
        }}>
          {warning}
        </div>
      )}
```

- [ ] **Step 10: Run all frontend tests**

```bash
cd frontend && npm test
```

Expected: all tests pass including the new warning banner test.

- [ ] **Step 11: Commit**

```bash
git add src/neurodb/api/schemas/study_log.py src/neurodb/api/routes/study_log.py \
        tests/unit/test_api_study_log.py \
        frontend/src/api/types.ts frontend/src/pages/StudyLogPanel.tsx \
        frontend/src/pages/StudyLogPanel.test.tsx
git commit -m "fix: embed study note in vector store on create (P1.1)"
```

---

## Task 3: P1.2 — Knowledge Library ChromaDB indexing on approve

**Files:**
- Modify: `src/neurodb/api/schemas/knowledge_library.py`
- Modify: `src/neurodb/api/routes/knowledge_library.py`
- Modify: `tests/unit/test_api_knowledge_library.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/pages/KnowledgeLibraryPanel.tsx`
- Modify: `frontend/src/pages/KnowledgeLibraryPanel.test.tsx`

Context: `POST /api/knowledge-library/{id}/approve` sets `status='approved'` but never indexes in ChromaDB. The `approve_source` route needs the `get_knowledge_store` dep and calls `knowledge_store.add_summary(...)` after the DB write. Row attributes must be captured inside the first session before it closes. `reject_source` is unchanged.

- [ ] **Step 1: Add `warnings` field to `KnowledgeSourceItem` schema**

Replace `src/neurodb/api/schemas/knowledge_library.py`:

```python
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
    warnings: list[str] = []
```

- [ ] **Step 2: Write failing Python tests**

Update `tests/unit/test_api_knowledge_library.py`. Replace `_make_app` and `_make_client` and add three new tests:

```python
from unittest.mock import MagicMock

# Replace the existing _make_app and _make_client:
def _make_app(engine, knowledge_store=None):
    app = FastAPI()
    app.state.engine = engine
    app.state.knowledge_store = knowledge_store if knowledge_store is not None else MagicMock()
    app.include_router(router, prefix="/api/knowledge-library")
    return app


def _make_client(knowledge_store=None):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine, knowledge_store)), engine
```

Add these tests at the end of the file:

```python
def test_approve_source_calls_add_summary():
    mock_ks = MagicMock()
    mock_ks.add_summary.return_value = "knowledge_source:1"
    client, engine = _make_client(mock_ks)
    _insert_source(engine, "LTP Paper", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/approve")

    assert resp.status_code == 200
    assert resp.json()["warnings"] == []
    mock_ks.add_summary.assert_called_once()


def test_approve_source_returns_warning_when_chroma_fails():
    mock_ks = MagicMock()
    mock_ks.add_summary.side_effect = RuntimeError("chroma down")
    client, engine = _make_client(mock_ks)
    _insert_source(engine, "LTP Paper", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/approve")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert len(data["warnings"]) == 1
    assert "ChromaDB indexing failed" in data["warnings"][0]


def test_reject_source_has_no_warnings_field_interaction():
    client, engine = _make_client()
    _insert_source(engine, "LTP Paper", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/reject")

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
```

- [ ] **Step 3: Run new tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_knowledge_library.py::test_approve_source_calls_add_summary tests/unit/test_api_knowledge_library.py::test_approve_source_returns_warning_when_chroma_fails -v
```

Expected: FAIL.

- [ ] **Step 4: Implement the route change**

Replace the entire `src/neurodb/api/routes/knowledge_library.py`:

```python
"""GET /api/knowledge-library and approve/reject routes."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from neurodb.api.deps import get_engine, get_knowledge_store
from neurodb.api.schemas.knowledge_library import KnowledgeSourceItem
from neurodb.db import get_session
from neurodb.schema import KnowledgeSource

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[KnowledgeSourceItem])
def get_knowledge_library(
    status: str = "all",
    engine: Engine = Depends(get_engine),
) -> list[KnowledgeSourceItem]:
    with get_session(engine) as session:
        query = session.query(KnowledgeSource)
        if status != "all":
            query = query.filter(KnowledgeSource.status == status)
        rows = query.order_by(KnowledgeSource.queued_at.desc()).all()
        return [KnowledgeSourceItem.model_validate(row) for row in rows]


@router.post("/{source_id}/approve", response_model=KnowledgeSourceItem)
def approve_source(
    source_id: int,
    engine: Engine = Depends(get_engine),
    knowledge_store=Depends(get_knowledge_store),
) -> KnowledgeSourceItem:
    reviewed_at = datetime.now(UTC).isoformat()
    warnings: list[str] = []
    with get_session(engine) as session:
        row = session.get(KnowledgeSource, source_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"KnowledgeSource {source_id} not found"
            )
        row.status = "approved"
        row.reviewed_at = reviewed_at
        session.flush()
        item = KnowledgeSourceItem.model_validate(row)
        # Capture scalar values before the session closes — ORM objects are detached after commit
        _id, _title, _doi, _topic, _summary = (
            row.id, row.title, row.doi, row.topic_context, row.summary
        )
    try:
        chroma_id = knowledge_store.add_summary(
            source_id=_id,
            title=_title,
            doi=_doi,
            topic_context=_topic,
            summary=_summary or "",
        )
        with get_session(engine) as session:
            row = session.get(KnowledgeSource, source_id)
            if row is not None:
                row.chroma_id = chroma_id
    except Exception as exc:
        logger.exception("ChromaDB indexing failed for source %d", source_id)
        warnings.append(f"ChromaDB indexing failed: {exc}")
    return item.model_copy(update={"warnings": warnings})


@router.post("/{source_id}/reject", response_model=KnowledgeSourceItem)
def reject_source(source_id: int, engine: Engine = Depends(get_engine)) -> KnowledgeSourceItem:
    return _set_status(source_id, "rejected", engine)


def _set_status(source_id: int, status: str, engine: Engine) -> KnowledgeSourceItem:
    reviewed_at = datetime.now(UTC).isoformat()
    with get_session(engine) as session:
        row = session.get(KnowledgeSource, source_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"KnowledgeSource {source_id} not found"
            )
        row.status = status
        row.reviewed_at = reviewed_at
        session.flush()
        return KnowledgeSourceItem.model_validate(row)
```

- [ ] **Step 5: Run all knowledge library tests**

```bash
uv run pytest tests/unit/test_api_knowledge_library.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Update `KnowledgeSourceItem` in `frontend/src/api/types.ts`**

```ts
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
  warnings?: string[]
}
```

- [ ] **Step 7: Write failing frontend test for warning banner**

Add to `frontend/src/pages/KnowledgeLibraryPanel.test.tsx` (add `fireEvent, waitFor, vi, afterEach` to imports):

```tsx
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, it, expect, vi } from 'vitest'

import KnowledgeLibraryPanel from './KnowledgeLibraryPanel'

function makeWrapper(data: unknown) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['knowledge-library', 'all'], data)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('KnowledgeLibraryPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows empty state', () => {
    render(<KnowledgeLibraryPanel />, { wrapper: makeWrapper([]) })
    expect(screen.getByText(/No sources/)).toBeTruthy()
  })

  it('renders pending source with approve and reject buttons', () => {
    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 1,
        title: 'LTP Review',
        doi: null,
        url: null,
        source_type: 'paper',
        topic_context: 'plasticity',
        status: 'pending',
        queued_at: '2026-01-01',
        reviewed_at: null,
        summary: null,
      }]),
    })
    expect(screen.getByText('LTP Review')).toBeTruthy()
    expect(screen.getByText('Approve')).toBeTruthy()
    expect(screen.getByText('Reject')).toBeTruthy()
  })

  it('shows warning banner when approve returns a warning', async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.includes('/approve') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 1,
            title: 'LTP Review',
            doi: null,
            url: null,
            source_type: 'paper',
            topic_context: 'plasticity',
            status: 'approved',
            queued_at: '2026-01-01',
            reviewed_at: '2026-05-12T00:00:00',
            summary: null,
            warnings: ['ChromaDB indexing failed: chroma down'],
          }),
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<KnowledgeLibraryPanel />, {
      wrapper: makeWrapper([{
        id: 1, title: 'LTP Review', doi: null, url: null,
        source_type: 'paper', topic_context: 'plasticity',
        status: 'pending', queued_at: '2026-01-01',
        reviewed_at: null, summary: null,
      }]),
    })
    fireEvent.click(screen.getByText('Approve'))

    await waitFor(() => {
      expect(screen.getByText(/ChromaDB indexing failed/)).toBeTruthy()
    })
  })
})
```

- [ ] **Step 8: Run frontend test to confirm it fails**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A3 "warning banner"
```

Expected: FAIL.

- [ ] **Step 9: Implement warning banner in `KnowledgeLibraryPanel.tsx`**

Replace the entire `frontend/src/pages/KnowledgeLibraryPanel.tsx`:

```tsx
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'

export default function KnowledgeLibraryPanel() {
  const [statusFilter, setStatusFilter] = useState('all')
  const [approveWarnings, setApproveWarnings] = useState<Record<number, string>>({})
  const queryClient = useQueryClient()

  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['knowledge-library', statusFilter],
    queryFn: () => api.getKnowledgeLibrary(statusFilter),
  })

  const approve = useMutation({
    mutationFn: (id: number) => api.approveSource(id),
    onSuccess: (data, id) => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-library'] })
      if (data.warnings?.length) {
        setApproveWarnings(prev => ({ ...prev, [id]: data.warnings![0] }))
      }
    },
  })
  const reject = useMutation({
    mutationFn: (id: number) => api.rejectSource(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge-library'] }),
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <h4>Knowledge Library</h4>
        <select
          value={statusFilter}
          onChange={event => setStatusFilter(event.target.value)}
          style={{ fontSize: 12, padding: '3px 6px', border: '1px solid #cbd5e1', borderRadius: 4 }}
        >
          <option value="all">All</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>
      {data.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No sources matching filter.</p>
      ) : data.map(item => (
        <div
          key={item.id}
          style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}
        >
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
          {item.status === 'pending' ? (
            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <button
                onClick={() => approve.mutate(item.id)}
                disabled={approve.isPending}
                style={{
                  fontSize: 12, padding: '3px 10px', cursor: 'pointer',
                  background: '#1e3a8a', color: '#fff', border: 'none', borderRadius: 4,
                }}
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
          ) : (
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
              {item.status} · {item.reviewed_at?.slice(0, 10) ?? ''}
            </div>
          )}
          {approveWarnings[item.id] && (
            <div style={{
              color: '#92400e', background: '#fef3c7',
              padding: '4px 8px', borderRadius: 4, fontSize: 11, marginTop: 4,
            }}>
              {approveWarnings[item.id]}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 10: Run all frontend tests**

```bash
cd frontend && npm test
```

Expected: all tests pass.

- [ ] **Step 11: Commit**

```bash
git add src/neurodb/api/schemas/knowledge_library.py src/neurodb/api/routes/knowledge_library.py \
        tests/unit/test_api_knowledge_library.py \
        frontend/src/api/types.ts \
        frontend/src/pages/KnowledgeLibraryPanel.tsx \
        frontend/src/pages/KnowledgeLibraryPanel.test.tsx
git commit -m "fix: index knowledge source in ChromaDB on approve (P1.2)"
```

---

## Task 4: P1.3 — ImportQueue status update on import completion

**Files:**
- Modify: `src/neurodb/api/routes/datasets.py`
- Modify: `tests/unit/test_api_datasets_import.py`

Context: The `run()` background thread sets the TaskRecord to `done` after `_ingest_dataset` completes, but never updates the `ImportQueue` row. A `SyncThread` helper in tests runs the thread synchronously so the DB state can be asserted without timing dependencies.

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/test_api_datasets_import.py`:

```python
from sqlalchemy import select
from neurodb.schema import ImportQueue

# Add these at the end of the file:

class _SyncThread:
    """Runs the target callable synchronously — used in tests to avoid timing issues."""
    def __init__(self, target, daemon=True):
        self._target = target
    def start(self):
        self._target()


def test_import_success_updates_import_queue_status():
    client, engine = _make_client()
    with get_session(engine) as session:
        session.add(ImportQueue(
            source="openneuro",
            source_id="ds001",
            title="Test Dataset",
            status="pending",
            suggested_at="2026-01-01T00:00:00",
        ))

    with patch("neurodb.api.routes.datasets._ingest_dataset"), \
         patch("neurodb.api.routes.datasets.threading.Thread", _SyncThread):
        resp = client.post("/api/datasets/openneuro/ds001/import")

    assert resp.status_code == 200
    with get_session(engine) as session:
        queue_row = session.execute(
            select(ImportQueue).where(
                ImportQueue.source == "openneuro",
                ImportQueue.source_id == "ds001",
            )
        ).scalars().first()
    assert queue_row is not None
    assert queue_row.status == "imported"
    assert queue_row.resolved_at is not None


def test_import_no_queue_row_still_marks_task_done():
    """No ImportQueue row for this dataset — import succeeds, task is done."""
    client, engine = _make_client()

    with patch("neurodb.api.routes.datasets._ingest_dataset"), \
         patch("neurodb.api.routes.datasets.threading.Thread", _SyncThread):
        resp = client.post("/api/datasets/openneuro/ds001/import")

    task_id = resp.json()["task_id"]
    assert client.app.state.tasks[task_id].status == "done"
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_datasets_import.py::test_import_success_updates_import_queue_status tests/unit/test_api_datasets_import.py::test_import_no_queue_row_still_marks_task_done -v
```

Expected: FAIL — `run()` doesn't update ImportQueue.

- [ ] **Step 3: Implement the `run()` change**

Replace the entire `src/neurodb/api/routes/datasets.py`:

```python
"""GET /api/datasets and dataset import routes."""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, select

from neurodb.api.deps import get_engine, get_task_store
from neurodb.api.schemas.datasets import DatasetItem
from neurodb.api.tasks import TaskRecord
from neurodb.db import get_session
from neurodb.schema import DatasetIndex, ImportQueue

logger = logging.getLogger(__name__)

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
    tasks: dict[str, TaskRecord] = Depends(get_task_store),
) -> dict[str, str]:
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
            return
        # Best-effort: mark the import queue row resolved.
        # Failure here must not override the successful task status.
        try:
            resolved_at = datetime.now(UTC).isoformat()
            with get_session(engine) as session:
                queue_row = session.execute(
                    select(ImportQueue).where(
                        ImportQueue.source == source,
                        ImportQueue.source_id == source_id,
                        ImportQueue.status == "pending",
                    )
                ).scalars().first()
                if queue_row is not None:
                    queue_row.status = "imported"
                    queue_row.resolved_at = resolved_at
        except Exception:
            logger.exception(
                "Failed to update ImportQueue status for %s:%s", source, source_id
            )

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

- [ ] **Step 4: Run all import tests**

```bash
uv run pytest tests/unit/test_api_datasets_import.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/datasets.py tests/unit/test_api_datasets_import.py
git commit -m "fix: update ImportQueue status to imported on background import success (P1.3)"
```

---

## Task 5: P1.4 + P1.5 — Promote `added_by` and suggestion type gating

**Files:**
- Modify: `src/neurodb/api/routes/suggestions.py`
- Modify: `tests/unit/test_api_suggestions.py`
- Modify: `frontend/src/pages/SuggestionsPanel.tsx`
- Modify: `frontend/src/pages/SuggestionsPanel.test.tsx`

Context: `promote_source_suggestion` hardcodes `added_by="suggestion"` — it should be `"user"`. The Promote button in React shows for all suggestion types; it should only appear for `suggestion_type === 'learning_source'` since only those rows have a well-formed `reference` (DOI/URL) and `display_name` suitable for a registry entry.

- [ ] **Step 1: Write failing Python test**

In `tests/unit/test_api_suggestions.py`, the existing test `test_promote_source_suggestion_creates_registry_entry_and_returns_item` currently asserts `data["added_by"] == "suggestion"`. Change that assertion and add a dedicated test:

Update the existing assertion:
```python
    assert data["added_by"] == "user"   # was "suggestion"
```

Add a new test:
```python
def test_promote_sets_added_by_user():
    client, engine = _make_client()
    with get_session(engine) as session:
        session.add(SourceSuggestion(
            suggestion_type="learning_source",
            reference="10.9999/test",
            display_name="LTP Meta-Analysis",
            reason="Relevant",
            status="pending",
            suggested_at="2026-01-01T00:00:00",
        ))
    item_id = client.get("/api/suggestions").json()["source_suggestions"][0]["id"]

    resp = client.post(f"/api/suggestions/source-suggestions/{item_id}/promote")

    assert resp.status_code == 200
    assert resp.json()["added_by"] == "user"
```

- [ ] **Step 2: Run the failing test**

```bash
uv run pytest tests/unit/test_api_suggestions.py::test_promote_sets_added_by_user -v
```

Expected: FAIL — currently returns `"suggestion"`.

- [ ] **Step 3: Fix `added_by` in the promote route**

In `src/neurodb/api/routes/suggestions.py`, line 79, change one word:

```python
        source = LearningSource(
            source_type=row.suggestion_type,
            source_key=source_key,
            display_name=row.display_name or source_key,
            added_by="user",   # was "suggestion"
            added_at=datetime.now(UTC).isoformat(),
        )
```

- [ ] **Step 4: Run all suggestions Python tests**

```bash
uv run pytest tests/unit/test_api_suggestions.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Write failing frontend test for Promote gating**

Replace `frontend/src/pages/SuggestionsPanel.test.tsx` with the full updated file:

```tsx
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import SuggestionsPanel from './SuggestionsPanel'

function makeWrapper(data: unknown) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  qc.setQueryData(['suggestions'], data)
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('SuggestionsPanel', () => {
  it('shows empty state when no suggestions', () => {
    render(<SuggestionsPanel />, {
      wrapper: makeWrapper({ import_queue: [], source_suggestions: [] }),
    })
    expect(screen.getByText(/No pending import suggestions/)).toBeTruthy()
  })

  it('renders import queue items', () => {
    render(<SuggestionsPanel />, {
      wrapper: makeWrapper({
        import_queue: [{
          id: 1, source: 'openneuro', source_id: 'ds001',
          title: 'Test DS', status: 'pending', suggested_at: '2026-01-01',
          reason: null, chapter_ref: null,
        }],
        source_suggestions: [],
      }),
    })
    expect(screen.getByText(/Test DS/)).toBeTruthy()
  })

  it('renders Dismiss and Promote for learning_source suggestions', () => {
    render(<SuggestionsPanel />, {
      wrapper: makeWrapper({
        import_queue: [],
        source_suggestions: [{
          id: 1,
          suggestion_type: 'learning_source',
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

  it('hides Promote for non-learning_source suggestion types', () => {
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
    expect(screen.queryByText('Promote')).toBeNull()
  })

  it('renders Import button on import queue items', () => {
    render(<SuggestionsPanel />, {
      wrapper: makeWrapper({
        import_queue: [{
          id: 1, source: 'openneuro', source_id: 'ds001',
          title: 'Test DS', status: 'pending', suggested_at: '2026-01-01',
          reason: null, chapter_ref: null,
        }],
        source_suggestions: [],
      }),
    })
    expect(screen.getByText('Import')).toBeTruthy()
  })
})
```

- [ ] **Step 6: Run frontend test to confirm the new test fails**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 "hides Promote"
```

Expected: FAIL — Promote currently shown for all suggestion types.

- [ ] **Step 7: Implement Promote gating in `SuggestionsPanel.tsx`**

In `frontend/src/pages/SuggestionsPanel.tsx`, in `SourceSuggestionRow`, wrap the Promote button in a conditional:

```tsx
      {item.suggestion_type === 'learning_source' && (
        <button
          onClick={() => promote.mutate()}
          disabled={promote.isPending}
          style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
        >
          Promote
        </button>
      )}
```

- [ ] **Step 8: Run all frontend tests**

```bash
cd frontend && npm test
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add src/neurodb/api/routes/suggestions.py tests/unit/test_api_suggestions.py \
        frontend/src/pages/SuggestionsPanel.tsx frontend/src/pages/SuggestionsPanel.test.tsx
git commit -m "fix: promote sets added_by=user; gate Promote to learning_source type (P1.4+P1.5)"
```

---

## Task 6: P1.6 — Registry topics and `added_by` hardcode

**Files:**
- Modify: `src/neurodb/api/routes/registry.py`
- Modify: `tests/unit/test_api_registry.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/pages/RegistryPanel.tsx`
- Modify: `frontend/src/pages/RegistryPanel.test.tsx`

Context: The registry add form has no topics field — all entries created via React have `content_json = null`. The form also exposes `added_by` as free text, producing inconsistent provenance. Fix: remove `added_by` from the request model (hardcode `"user"` in the route), add `topics: list[str] | None` (serialized to `content_json`).

- [ ] **Step 1: Write failing Python tests**

Add to `tests/unit/test_api_registry.py`:

```python
import json

def test_post_registry_with_topics_serializes_content_json():
    client, _ = _make_client()

    resp = client.post("/api/registry", json={
        "source_type": "paper",
        "source_key": "doi:10.1234/topics",
        "display_name": "LTP Topics Paper",
        "topics": ["LTP", "synaptic plasticity", "hippocampus"],
    })

    assert resp.status_code == 200
    with get_session(_make_client()[1]) as session:
        pass
    # Verify via direct DB query
    client2, engine2 = _make_client()
    client2.post("/api/registry", json={
        "source_type": "paper",
        "source_key": "doi:10.9999/verify",
        "display_name": "Verify Paper",
        "topics": ["plasticity"],
    })
    from sqlalchemy import select as sa_select
    from neurodb.schema import LearningSource as LS
    with get_session(engine2) as s:
        row = s.execute(sa_select(LS).where(LS.source_key == "doi:10.9999/verify")).scalar_one()
    parsed = json.loads(row.content_json)
    assert parsed["topics"] == ["plasticity"]
    assert row.added_by == "user"


def test_post_registry_without_topics_has_null_content_json():
    client, engine = _make_client()

    client.post("/api/registry", json={
        "source_type": "paper",
        "source_key": "doi:10.5555/notopics",
        "display_name": "No Topics Paper",
    })

    from sqlalchemy import select as sa_select
    from neurodb.schema import LearningSource as LS
    with get_session(engine) as s:
        row = s.execute(sa_select(LS).where(LS.source_key == "doi:10.5555/notopics")).scalar_one()
    assert row.content_json is None


def test_post_registry_added_by_is_always_user():
    """Sending added_by in body is ignored — route hardcodes "user"."""
    client, _ = _make_client()

    resp = client.post("/api/registry", json={
        "source_type": "paper",
        "source_key": "doi:10.1111/provenance",
        "display_name": "Provenance Test",
        "added_by": "bot",   # this field is now ignored
    })

    assert resp.status_code == 200
    assert resp.json()["added_by"] == "user"
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_registry.py::test_post_registry_with_topics_serializes_content_json tests/unit/test_api_registry.py::test_post_registry_without_topics_has_null_content_json tests/unit/test_api_registry.py::test_post_registry_added_by_is_always_user -v
```

Expected: FAIL.

- [ ] **Step 3: Implement backend registry change**

Replace the entire `src/neurodb/api/routes/registry.py`:

```python
"""GET, POST, and DELETE /api/registry routes."""
from __future__ import annotations

import json
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
    topics: list[str] | None = None


@router.post("", response_model=LearningSourceItem)
def create_registry_entry(
    body: CreateRegistryRequest,
    engine: Engine = Depends(get_engine),
) -> LearningSourceItem:
    content_json = json.dumps({"topics": body.topics}) if body.topics else None
    with get_session(engine) as session:
        source = LearningSource(
            source_type=body.source_type,
            source_key=body.source_key,
            display_name=body.display_name,
            content_json=content_json,
            added_by="user",
            added_at=datetime.now(UTC).isoformat(),
        )
        session.add(source)
        try:
            session.flush()
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="source_key already exists") from exc
        return LearningSourceItem.model_validate(source)
```

- [ ] **Step 4: Run all registry Python tests**

```bash
uv run pytest tests/unit/test_api_registry.py -v
```

Expected: all tests pass. (The existing `test_post_registry_creates_source_and_returns_item` sends `added_by: "user"` in the body — Pydantic v2 silently ignores extra fields, so it still passes.)

- [ ] **Step 5: Update `CreateLearningSourceRequest` in `frontend/src/api/types.ts`**

```ts
export interface CreateLearningSourceRequest {
  source_type: string
  source_key: string
  display_name: string
  topics?: string[]
}
```

- [ ] **Step 6: Write failing frontend tests for the registry form**

Replace `frontend/src/pages/RegistryPanel.test.tsx` with the full updated file:

```tsx
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

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
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/registry/1' && init?.method === 'DELETE') {
        return Promise.resolve({
          ok: true, status: 204,
          text: async () => '', json: async () => undefined,
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] })
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

  it('add-source form has topics field and no added_by field', () => {
    render(<RegistryPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Source'))
    expect(screen.getByPlaceholderText(/topics/i)).toBeTruthy()
    expect(screen.queryByPlaceholderText('added by')).toBeNull()
  })

  it('add-source form submits POST /api/registry with topics', async () => {
    const newItem = {
      id: 99, source_type: 'paper', source_key: 'doi:new',
      display_name: 'New Paper', added_by: 'user', added_at: '2026-01-01T00:00:00',
    }
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/registry' && init?.method === 'POST') {
        return Promise.resolve({ ok: true, status: 200, json: async () => newItem })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => [] })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<RegistryPanel />, { wrapper: makeWrapper([]) })
    fireEvent.click(screen.getByText('Add Source'))
    fireEvent.change(screen.getByPlaceholderText('source key'), { target: { value: 'doi:new' } })
    fireEvent.change(screen.getByPlaceholderText('display name'), { target: { value: 'New Paper' } })
    fireEvent.change(screen.getByPlaceholderText(/topics/i), {
      target: { value: 'LTP, plasticity' },
    })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/registry',
        expect.objectContaining({ method: 'POST' }),
      )
      const body = JSON.parse(
        (fetchMock.mock.calls.find(([p, i]: [string, RequestInit]) =>
          p === '/api/registry' && i?.method === 'POST'
        )![1] as RequestInit).body as string
      )
      expect(body.topics).toEqual(['LTP', 'plasticity'])
      expect(body.added_by).toBeUndefined()
    })
  })
})
```

- [ ] **Step 7: Run frontend tests to confirm the new tests fail**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -E "(FAIL|topics|added_by)"
```

Expected: the two new tests fail.

- [ ] **Step 8: Implement registry frontend changes**

Replace the entire `frontend/src/pages/RegistryPanel.tsx`:

```tsx
import { useState, type FormEvent } from 'react'
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
            gap: 8,
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
  const [form, setForm] = useState({
    source_type: 'paper',
    source_key: '',
    display_name: '',
    topics_raw: '',
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
      setForm({ source_type: 'paper', source_key: '', display_name: '', topics_raw: '' })
    },
  })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    const topics = form.topics_raw
      .split(',')
      .map(t => t.trim())
      .filter(t => t.length > 0)
    create.mutate({
      source_type: form.source_type,
      source_key: form.source_key,
      display_name: form.display_name,
      topics: topics.length > 0 ? topics : undefined,
    })
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
        onClick={() => setShowForm(value => !value)}
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
            onChange={event => setForm(current => ({ ...current, source_type: event.target.value }))}
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
            onChange={event => setForm(current => ({ ...current, source_key: event.target.value }))}
            placeholder="source key"
            required
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          <input
            value={form.display_name}
            onChange={event => setForm(current => ({ ...current, display_name: event.target.value }))}
            placeholder="display name"
            required
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          <textarea
            value={form.topics_raw}
            onChange={event => setForm(current => ({ ...current, topics_raw: event.target.value }))}
            placeholder="topics (comma separated, optional)"
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

- [ ] **Step 9: Run all frontend tests**

```bash
cd frontend && npm test
```

Expected: all tests pass.

- [ ] **Step 10: Run full Python test suite**

```bash
uv run pytest tests/ -q
```

Expected: no new failures beyond those in `docs/testLog.md`.

- [ ] **Step 11: Commit**

```bash
git add src/neurodb/api/routes/registry.py tests/unit/test_api_registry.py \
        frontend/src/api/types.ts \
        frontend/src/pages/RegistryPanel.tsx frontend/src/pages/RegistryPanel.test.tsx
git commit -m "fix: registry add form persists topics to content_json; hardcode added_by=user (P1.6)"
```

---

## Self-Review Checklist

Run this after all 6 tasks are complete:

```bash
uv run pytest tests/ -q          # Python — no new failures
cd frontend && npm test           # Frontend — all pass
cd frontend && npm run build      # TypeScript — no type errors
```
