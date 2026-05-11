# UI-3 Parity Migration Design

**Date:** 2026-05-11
**Status:** Approved
**Author:** Eric Herrmann

---

## Goal

Add all missing write operations to the React workbench so every Streamlit surface has a functional React equivalent. Demote Streamlit to secondary (banner only) at the end of the phase. UI-4 will make the final retirement decision.

---

## Parity Gap

All 7 React panels exist and all reads are functional. The gap is entirely in write operations:

| Missing action | Streamlit page | Missing API route |
|---|---|---|
| Create study tag | Study Log + Datasets | `POST /api/study-log` |
| Dismiss source suggestion | Suggestions | `POST /api/suggestions/source-suggestions/{id}/dismiss` |
| Promote source suggestion → Registry | Suggestions | `POST /api/suggestions/source-suggestions/{id}/promote` |
| Remove registry entry | Registry | `DELETE /api/registry/{id}` |
| Add registry entry manually | Registry | `POST /api/registry` |
| Import dataset (trigger ingest) | Datasets | `POST /api/datasets/{source}/{source_id}/import` |
| Run hypothesis review | Research | `POST /api/research/hypotheses/{id}/review` |

---

## Architecture

### Background Task System

Import and hypothesis review are long-running operations (expected max ~60s each). They run as background tasks with polling feedback.

**`src/neurodb/api/tasks.py`** — task record and in-memory store. A `get_task_store` dependency function (in `api/deps.py`, same pattern as `get_engine`) returns `request.app.state.tasks` so route handlers don't access `app.state` directly.

```python
@dataclass
class TaskRecord:
    task_id: str
    status: Literal['running', 'done', 'failed']
    result: dict | None
    error: str | None
    started_at: str
    timeout_at: str          # ISO timestamp: started_at + max_seconds
```

`app.state.tasks: dict[str, TaskRecord]` is initialised to `{}` by `app_factory`.

**Task lifecycle:**
1. Heavy route generates a UUID task_id, inserts `TaskRecord(status='running', timeout_at=now+180s)`, starts a `threading.Thread`, returns `{"task_id": "..."}` immediately.
2. Background thread runs the operation inside `try/except`. On completion it sets `status='done'` + `result`; on exception it sets `status='failed'` + `error`.
3. `GET /api/tasks/{task_id}` reads from `app.state.tasks`. Before returning, if `status == 'running'` and `now > timeout_at`, it returns `{status: 'failed', error: 'Timed out'}`.

**Timeouts:**

| Operation | Expected max | Server timeout |
|---|---|---|
| Dataset import | ~60s | 180s |
| Hypothesis review | ~60s | 180s |

### React Task Polling

**`frontend/src/hooks/useTask.ts`**

```ts
interface TaskState {
  status: 'idle' | 'running' | 'done' | 'failed'
  result: unknown
  error: string | null
}

function useTask(
  taskId: string | null,
  timeoutMs: number,
  onSuccess?: (result: unknown) => void,
): TaskState
```

- Records `startedAt = Date.now()` when `taskId` first becomes non-null.
- Polls `GET /api/tasks/{taskId}` every 2s via `setInterval`.
- Stops polling when status is `done` or `failed`, or when `Date.now() - startedAt > timeoutMs`.
- On client-side timeout: sets `status='failed'`, `error='Timed out'`, stops polling.
- Calls `onSuccess(result)` when status becomes `done`.

**`frontend/src/components/TaskStatus.tsx`**

```ts
interface TaskStatusProps {
  status: 'idle' | 'running' | 'done' | 'failed'
  error: string | null
  successMessage: string
}
```

- `running` → spinner + "Running…"
- `done` → green text + `successMessage`
- `failed` → red text + `error`
- `idle` → renders nothing

---

## New API Routes

### `POST /api/study-log`

**File:** `src/neurodb/api/routes/study_log.py`

Request body:
```json
{ "source": "openneuro", "source_id": "ds000001", "concept_tag": "LTP", "section_ref": "Ch3", "note_text": "..." }
```

- `source` and `concept_tag` are required; 422 if missing.
- Creates a `StudyNote` row via the existing `tag_dataset` helper.
- Returns the created `StudyNoteItem`.

### `POST /api/suggestions/source-suggestions/{id}/dismiss`

**File:** `src/neurodb/api/routes/suggestions.py`

- Sets `SourceSuggestion.status = 'dismissed'`, sets `resolved_at`.
- Returns 204. Returns 404 if not found.

### `POST /api/suggestions/source-suggestions/{id}/promote`

**File:** `src/neurodb/api/routes/suggestions.py`

- Creates a `LearningSource` row from the suggestion fields (`display_name`, `source_key`, `source_type`). Sets `added_by = 'suggestion'`, `added_at = now`.
- Sets `SourceSuggestion.status = 'promoted'`, sets `resolved_at`.
- Returns the new `LearningSourceItem`. Returns 404 if not found.

### `DELETE /api/registry/{id}`

**File:** `src/neurodb/api/routes/registry.py`

- Deletes the `LearningSource` row.
- Returns 204. Returns 404 if not found.

### `POST /api/registry`

**File:** `src/neurodb/api/routes/registry.py`

Request body:
```json
{ "source_type": "paper", "source_key": "doi:10.1016/...", "display_name": "LTP Review", "added_by": "user" }
```

- All four fields required; 422 if missing.
- Creates a `LearningSource` row with `added_at = now`.
- Returns the created `LearningSourceItem`.

### `POST /api/datasets/{source}/{source_id}/import`

**File:** `src/neurodb/api/routes/datasets.py`

- Validates that the dataset exists in the DB (404 if not).
- Creates `TaskRecord(status='running', timeout_at=now+180s)`.
- Starts background thread: runs the ingest connector for `source`/`source_id`.
- Returns `{"task_id": "..."}` immediately.

### `POST /api/research/hypotheses/{id}/review`

**File:** `src/neurodb/api/routes/research.py`

- Validates that the hypothesis exists (404 if not).
- Creates `TaskRecord(status='running', timeout_at=now+180s)`.
- Starts background thread: calls `run_hypothesis_review(hypothesis_id, engine, router)`.
- Returns `{"task_id": "..."}` immediately.

### `GET /api/tasks/{task_id}`

**File:** `src/neurodb/api/routes/tasks.py` (new)

- Returns the `TaskRecord` as JSON.
- If `status == 'running'` and `now > timeout_at`, returns `{status: 'failed', error: 'Timed out'}`.
- Returns 404 if `task_id` not in `app.state.tasks`.

---

## React Panel Changes

### `StudyLogPanel.tsx`

Under the "Study Tags" view, add an "Add Tag" toggle button below the table. Clicking it shows/hides the form inline (local `showForm` state). Form fields:

Fields: source (select: openneuro / pubmed / arxiv), source_id (text, required), concept_tag (text, required), section_ref (text, optional), note_text (textarea, optional).

- Submit calls `POST /api/study-log`.
- On success: invalidates `['study-log']`, clears the form.
- Inline error if concept_tag is empty on submit.

### `SuggestionsPanel.tsx`

Source suggestions section currently renders read-only rows. Add per-row action buttons:

- **Dismiss** → `POST /api/suggestions/source-suggestions/{id}/dismiss` → invalidates `['suggestions']`
- **Promote** → `POST /api/suggestions/source-suggestions/{id}/promote` → invalidates `['suggestions']`, `['registry']`

Import queue: the **Dismiss** button already works. Add an **Import** button per row:
- Fires `POST /api/datasets/{source}/{source_id}/import`.
- Stores returned `task_id` in local state.
- Renders `<TaskStatus>` inline with `timeoutMs=180000` and `successMessage="Import complete"`.
- On success: invalidates `['datasets']`.

### `RegistryPanel.tsx`

Per source item: add a **Remove** button → `DELETE /api/registry/{id}` → invalidates `['registry']`.

Below the source groups, add an "Add Source" toggle button. Clicking it shows/hides the form inline (local `showForm` state). Form fields:

Fields: source_type (select: book / paper / dataset / arxiv / other), source_key (text, required), display_name (text, required), added_by (text, required).

- Submit calls `POST /api/registry`.
- On success: invalidates `['registry']`, clears form.

### `ResearchPanel.tsx`

Per hypothesis card: add a **Run Review** button.
- Fires `POST /api/research/hypotheses/{id}/review`.
- Stores returned `task_id` in local state.
- Renders `<TaskStatus>` inline with `timeoutMs=180000` and `successMessage="Review complete"`.
- On success: invalidates `['research-hypotheses']`.

---

## File Map

| Change | File |
|--------|------|
| New | `src/neurodb/api/tasks.py` |
| New | `src/neurodb/api/routes/tasks.py` |
| New | `src/neurodb/api/routes/registry.py` |
| Modify | `src/neurodb/api/routes/study_log.py` |
| Modify | `src/neurodb/api/routes/suggestions.py` |
| Modify | `src/neurodb/api/routes/datasets.py` |
| Modify | `src/neurodb/api/routes/research.py` |
| Modify | `src/neurodb/api/app.py` |
| New | `frontend/src/hooks/useTask.ts` |
| New | `frontend/src/hooks/useTask.test.ts` |
| New | `frontend/src/components/TaskStatus.tsx` |
| New | `frontend/src/components/TaskStatus.test.tsx` |
| Modify | `frontend/src/pages/StudyLogPanel.tsx` |
| Modify | `frontend/src/pages/SuggestionsPanel.tsx` |
| Modify | `frontend/src/pages/RegistryPanel.tsx` |
| Modify | `frontend/src/pages/ResearchPanel.tsx` |
| Modify | `frontend/src/api/client.ts` |
| Modify | `frontend/src/api/types.ts` |
| New test | `frontend/src/pages/RegistryPanel.test.tsx` |
| New test | `frontend/src/pages/ResearchPanel.test.tsx` |
| Modify test | `frontend/src/pages/StudyLogPanel.test.tsx` |
| Modify test | `frontend/src/pages/SuggestionsPanel.test.tsx` |
| New | `tests/unit/test_api_tasks.py` |
| New | `tests/unit/test_api_registry.py` |
| New | `tests/unit/test_api_datasets_import.py` |
| New | `tests/unit/test_api_research_review.py` |
| Modify | `tests/unit/test_api_study_log.py` |
| Modify | `tests/unit/test_api_suggestions.py` |
| Modify | `src/neurodb/ui/app.py` |
| Modify | `docs/projectStatus.md` |
| Modify | `docs/UI_EpochPlan.md` |

---

## Testing

### Python

| File | Tests |
|------|-------|
| `test_api_study_log.py` | Add: POST creates tag and returns item; POST returns 422 on missing concept_tag |
| `test_api_suggestions.py` | Add: source-suggestion dismiss returns 204; promote creates registry row and returns item |
| `test_api_registry.py` | New: DELETE removes row and returns 204; DELETE returns 404 for unknown id; POST creates row and returns item; POST returns 422 on missing field |
| `test_api_datasets_import.py` | New: POST returns task_id with status running (background thread mocked) |
| `test_api_research_review.py` | New: POST returns task_id with status running (review function mocked) |
| `test_api_tasks.py` | New: GET returns 404 for unknown id; GET returns record; GET returns failed when timeout_at in past |

### Frontend

| File | Tests |
|------|-------|
| `useTask.test.ts` | New: polls while running; stops on done and calls onSuccess; stops and returns failed on timeout |
| `TaskStatus.test.tsx` | New: renders spinner when running; renders success message when done; renders error text when failed |
| `StudyLogPanel.test.tsx` | Add: add-tag form submits POST /api/study-log; inline error on missing concept_tag |
| `SuggestionsPanel.test.tsx` | Add: promote fires correct route; Import button renders TaskStatus |
| `RegistryPanel.test.tsx` | New: renders source groups; remove fires DELETE; add-source form submits POST /api/registry |
| `ResearchPanel.test.tsx` | New: run review fires POST; TaskStatus renders after click |

### Manual test plan

Created before implementation begins in `docs/testsPlans/manualTestPlan_ui3_parity_migration.md`. Covers all 7 new write operations plus the Streamlit deprecation banner.

---

## Streamlit Deprecation

**`src/neurodb/ui/app.py`** — add banner at top of app (after `st.set_page_config`):

```python
st.info("The React workbench at http://localhost:5173 is now the primary UI. This Streamlit app will be retired in UI-4.")
```

No other Streamlit changes. Code is preserved for UI-4 retirement decision.

---

## Out of Scope (UI-3)

- Streamlit code deletion (UI-4)
- Study tag editing (row-select + prefill form from Streamlit study_log.py) — read-only parity is sufficient; edit-in-place is a UX enhancement
- Dataset tag form in DatasetsPanel (Streamlit had a duplicate tag form there; single form in StudyLogPanel is sufficient)
- Research question create/update actions
- Provider selection UI
- Monaco editor for SQL panel
