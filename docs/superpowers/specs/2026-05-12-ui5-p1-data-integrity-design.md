# UI-5 P1: Data Integrity Fixes — Design

**Date:** 2026-05-12
**Status:** Approved
**Author:** Eric Herrmann
**Parent:** `docs/superpowers/specs/2026-05-12-ui5-parity-completion-design.md`

---

## Goal

Fix the six data-integrity gaps introduced during UI-2/UI-3 where React writes incomplete or inconsistent data compared to Streamlit. All six must be resolved before UI-4 (Streamlit retirement) can proceed.

---

## Warning Propagation Pattern

P1.1 and P1.2 involve a primary DB write followed by a vector store side effect. The pattern used throughout:

- The DB write is the primary operation. If it fails, the route returns an error as normal.
- The vector store call is wrapped in `try/except Exception`. On exception, log server-side and append a human-readable string to a `warnings` field in the response. The HTTP status is still 200/201.
- Response schemas for affected endpoints gain `warnings: list[str] = []`. The default is empty, so GET endpoints are unaffected.
- React: after a successful mutation, if `data.warnings.length > 0`, render a yellow inline warning banner. The banner persists until the next action or component unmount.

---

## P1.1 — Study Log: Vector Embedding on Create

### Problem

`POST /api/study-log` creates the `StudyNote` DB row via `tag_dataset` but never calls `embed_note`. Study tags created via React are invisible to semantic search.

### Backend changes

**`src/neurodb/api/deps.py`** — add:

```python
def get_vector_store(request: Request):
    return request.app.state.vector_store
```

**`src/neurodb/api/routes/study_log.py`** — wire the new dep and embed after create:

```python
import logging
from neurodb.api.deps import get_engine, get_vector_store
from neurodb.embed_hooks import embed_note

logger = logging.getLogger(__name__)

@router.post("/study-log", response_model=StudyNoteItem)
def create_study_note(
    body: CreateStudyNoteRequest,
    engine: Engine = Depends(get_engine),
    vector_store=Depends(get_vector_store),
) -> StudyNoteItem:
    with get_session(engine) as session:
        note = tag_dataset(...)
        if note is None:
            raise HTTPException(status_code=404, ...)
        item = StudyNoteItem(id=note.id, ...)
        note_id = note.id  # capture before session closes — detached after context exit
    warnings: list[str] = []
    try:
        embed_note(vector_store, note_id, body.source, body.source_id,
                   body.concept_tag, body.section_ref, body.note_text)
    except Exception as exc:
        logger.exception("embed_note failed for note %d", note_id)
        warnings.append(f"Vector embedding failed: {exc}")
    return item.model_copy(update={"warnings": warnings})
```

**`src/neurodb/api/schemas/study_log.py`** — add warnings field:

```python
class StudyNoteItem(BaseModel):
    ...
    warnings: list[str] = []
```

### Frontend changes

**`frontend/src/pages/StudyLogPanel.tsx`** — in `StudyTagsView`, after `create.mutate` succeeds, render an inline warning if present:

```tsx
{create.isSuccess && (create.data as any).warnings?.length > 0 && (
  <div style={{ color: '#92400e', background: '#fef3c7', padding: '4px 8px',
                borderRadius: 4, fontSize: 11, marginTop: 4 }}>
    {(create.data as any).warnings[0]}
  </div>
)}
```

The `StudyNoteItem` type in `types.ts` gains `warnings?: string[]`.

---

## P1.2 — Knowledge Library: ChromaDB Indexing on Approve

### Problem

`POST /api/knowledge-library/{id}/approve` sets `status='approved'` but does not call `knowledge_store.add_summary`. Sources approved via React are never indexed in ChromaDB and are invisible to semantic search.

### Backend changes

**`src/neurodb/api/deps.py`** — add:

```python
def get_knowledge_store(request: Request):
    return request.app.state.knowledge_store
```

**`src/neurodb/api/routes/knowledge_library.py`** — wire dep, index on approve:

```python
import logging
from neurodb.api.deps import get_engine, get_knowledge_store

logger = logging.getLogger(__name__)

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
            raise HTTPException(status_code=404, ...)
        row.status = "approved"
        row.reviewed_at = reviewed_at
        session.flush()
        item = KnowledgeSourceItem.model_validate(row)
        # Extract values before session closes — row is detached after context exit
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
```

`reject_source` is unchanged — no indexing on reject.

**Note on `summary=None` at approve time:** LLM summary generation is P2. Passing `summary=""` means the item is indexed by title and topic_context only. P2 will update the embedding when the summary is generated.

**`src/neurodb/api/schemas/knowledge_library.py`** — add warnings field:

```python
class KnowledgeSourceItem(BaseModel):
    ...
    warnings: list[str] = []
```

### Frontend changes

**`frontend/src/pages/KnowledgeLibraryPanel.tsx`** — after `approve.mutate(id)` succeeds, show inline warning per item if present. Track per-item warning in local state:

```tsx
const [approveWarning, setApproveWarning] = useState<Record<number, string>>({})

const approve = useMutation({
  mutationFn: (id: number) => api.approveSource(id),
  onSuccess: (data, id) => {
    queryClient.invalidateQueries({ queryKey: ['knowledge-library'] })
    if (data.warnings?.length) {
      setApproveWarning(prev => ({ ...prev, [id]: data.warnings[0] }))
    }
  },
})
```

Render the warning below the Approve button for the relevant item.

`KnowledgeSourceItem` in `types.ts` gains `warnings?: string[]`.

---

## P1.3 — Datasets: ImportQueue Status on Import Completion

### Problem

The background thread in `POST /api/datasets/{source}/{source_id}/import` runs `_ingest_dataset` and marks the TaskRecord `done`, but never updates `ImportQueue.status`. Imported items remain `'pending'` indefinitely.

### Backend changes

**`src/neurodb/api/routes/datasets.py`** — in the `run()` closure, after `_ingest_dataset` returns, update the queue row:

```python
def run() -> None:
    try:
        _ingest_dataset(source, source_id, engine)
        tasks[task_id].status = "done"
        tasks[task_id].result = {"imported": True}
    except Exception as exc:
        tasks[task_id].status = "failed"
        tasks[task_id].error = str(exc)[:400]
        return
    # Best-effort queue status update — failure must not override task success
    try:
        resolved_at = datetime.now(UTC).isoformat()
        with get_session(engine) as session:
            row = session.execute(
                select(ImportQueue).where(
                    ImportQueue.source == source,
                    ImportQueue.source_id == source_id,
                    ImportQueue.status == "pending",
                )
            ).scalars().first()  # multiple pending rows possible; update the first
            if row is not None:
                row.status = "imported"
                row.resolved_at = resolved_at
    except Exception:
        logger.exception(
            "Failed to update ImportQueue status for %s:%s", source, source_id
        )
```

No frontend or schema changes. The queue row update is internal bookkeeping; the user observes success via the existing TaskStatus component.

---

## P1.4 — Suggestions: `added_by` on Promote

### Problem

`promote_source_suggestion` hardcodes `added_by="suggestion"`. The human pressed Promote, so the record should be tagged `"user"`.

### Backend changes

**`src/neurodb/api/routes/suggestions.py`** — one-line change:

```python
# before
added_by="suggestion",
# after
added_by="user",
```

No frontend or schema changes.

---

## P1.5 — Suggestions: Promote Gating by Suggestion Type

### Problem

`SourceSuggestionRow` renders the Promote button for all suggestion types. Promoting a `dataset` suggestion uses `row.reference` as `source_key`, which is a dataset ID rather than a DOI or URL — producing a corrupt registry entry. Only `learning_source` type suggestions have well-formed `reference` + `display_name` fields for registry promotion.

### Frontend changes

**`frontend/src/pages/SuggestionsPanel.tsx`** — in `SourceSuggestionRow`, gate the Promote button:

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

No backend changes.

---

## P1.6 — Registry: Topics Field and `added_by` Hardcode

### Problem

1. The `POST /api/registry` add form has no topics field. Every entry created via React has `content_json = null`, discarding structured topic data.
2. The form exposes `added_by` as a free-text input, producing inconsistent provenance strings. It should always be `"user"` when created through the UI.

### Backend changes

**`src/neurodb/api/routes/registry.py`** — update `CreateRegistryRequest` and the route:

```python
import json

class CreateRegistryRequest(BaseModel):
    source_type: str
    source_key: str
    display_name: str
    topics: list[str] | None = None
    # added_by removed — hardcoded to "user" below

@router.post("", response_model=LearningSourceItem)
def create_registry_entry(
    body: CreateRegistryRequest,
    engine: Engine = Depends(get_engine),
) -> LearningSourceItem:
    content_json = (
        json.dumps({"topics": body.topics})
        if body.topics
        else None
    )
    with get_session(engine) as session:
        source = LearningSource(
            source_type=body.source_type,
            source_key=body.source_key,
            display_name=body.display_name,
            content_json=content_json,
            added_by="user",
            added_at=datetime.now(UTC).isoformat(),
        )
        ...
```

Existing callers that send `added_by` in the request body are unaffected — Pydantic ignores extra fields.

### Frontend changes

**`frontend/src/api/types.ts`** — update `CreateLearningSourceRequest`:

```ts
export interface CreateLearningSourceRequest {
  source_type: string
  source_key: string
  display_name: string
  topics?: string[]
}
```

**`frontend/src/pages/RegistryPanel.tsx`**:
- Remove `added_by` from form state and the `added_by` input field.
- Add a topics textarea (optional). On submit, split by comma, trim, filter empty: `topics: string[] | undefined`.
- Update `CreateLearningSourceRequest` type reference accordingly.

---

## File Map

| Change | File |
|---|---|
| Modify | `src/neurodb/api/deps.py` |
| Modify | `src/neurodb/api/routes/study_log.py` |
| Modify | `src/neurodb/api/schemas/study_log.py` |
| Modify | `src/neurodb/api/routes/knowledge_library.py` |
| Modify | `src/neurodb/api/schemas/knowledge_library.py` |
| Modify | `src/neurodb/api/routes/datasets.py` |
| Modify | `src/neurodb/api/routes/suggestions.py` |
| Modify | `src/neurodb/api/routes/registry.py` |
| Modify | `frontend/src/api/types.ts` |
| Modify | `frontend/src/pages/StudyLogPanel.tsx` |
| Modify | `frontend/src/pages/KnowledgeLibraryPanel.tsx` |
| Modify | `frontend/src/pages/SuggestionsPanel.tsx` |
| Modify | `frontend/src/pages/RegistryPanel.tsx` |

---

## Testing

### Python

| File | Tests |
|---|---|
| `tests/unit/test_api_study_log.py` | Add: POST embeds note (mock embed_note called); POST returns warning when embed_note raises |
| `tests/unit/test_api_knowledge_library.py` | Add: approve calls add_summary (mock); approve returns warning when add_summary raises; approve sets chroma_id |
| `tests/unit/test_api_datasets_import.py` | Add: import success updates ImportQueue status to "imported"; ImportQueue update failure does not flip task to failed |
| `tests/unit/test_api_suggestions.py` | Add: promote sets added_by="user" |
| `tests/unit/test_api_registry.py` | Add: POST with topics serialises content_json; POST without topics leaves content_json null; added_by is always "user" |

### Frontend

| File | Tests |
|---|---|
| `frontend/src/pages/StudyLogPanel.test.tsx` | Add: warning banner shown when create returns warnings |
| `frontend/src/pages/KnowledgeLibraryPanel.test.tsx` | Add: warning banner shown when approve returns warnings |
| `frontend/src/pages/SuggestionsPanel.test.tsx` | Add: Promote button absent for non-learning_source suggestions |
| `frontend/src/pages/RegistryPanel.test.tsx` | Add: add-source form has topics field; added_by field absent; topics sent in POST body |

---

## Out of Scope

- `DELETE /api/study-log/{id}` + `remove_note` (P2 delete tag feature)
- `content_json` in `LearningSourceItem` GET response (P3 content expansion)
- `chroma_id` in `KnowledgeSourceItem` GET response (internal field)
- LLM summary generation on approve (P2)
- Near-duplicate detection (P2)
