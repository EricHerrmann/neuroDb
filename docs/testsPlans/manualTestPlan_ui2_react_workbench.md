# Manual Test Plan - UI-2: React Workbench Migration

**Epoch scope:** UI - FastAPI backend routes plus Vite/React workbench replacing the Streamlit UI surface.
**Phase:** UI-2
**Design source:** `docs/superpowers/specs/2026-05-11-ui2-react-workbench-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-05-11-ui2-react-workbench.md`
**Status:** Draft - in progress
**Date:** 2026-05-11

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. `.env` exists and contains the provider keys needed for chat verification.
2. Automated backend tests pass for UI-2 route work:

```bash
uv run pytest tests/unit/test_api_study_log.py tests/unit/test_api_sessions.py tests/unit/test_api_suggestions.py -q
```

3. After frontend scaffold lands, automated frontend tests pass:

```bash
cd frontend
npm test -- --run
```

4. Start the FastAPI server after Task 8:

```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
```

5. Start the Vite dev server after Task 9:

```bash
cd frontend
npm run dev
```

---

## Backend API Evals

### T1 - Study log API returns tagged studies

```bash
curl -s http://localhost:8001/api/study-log | python3 -m json.tool
```

**Pass:** Response is a JSON array. Items include `id`, `source`, `source_id`, `concept_tag`, and `tagged_at`.

### T2 - Sessions API returns recent sessions

```bash
curl -s http://localhost:8001/api/sessions | python3 -m json.tool
```

**Pass:** Response is a JSON array ordered newest first. Items include `session_id`, `inferred_topic`, `agent_mode`, `started_at`, and `message_count`.

### T3 - Suggestions API returns pending queues

```bash
curl -s http://localhost:8001/api/suggestions | python3 -m json.tool
```

**Pass:** Response contains `import_queue` and `source_suggestions` arrays. Only pending rows are returned.

### T4 - Suggestions dismiss API removes an import queue item from pending view

```bash
curl -s -X POST http://localhost:8001/api/suggestions/import-queue/{id}/dismiss -i
curl -s http://localhost:8001/api/suggestions | python3 -m json.tool
```

**Pass:** POST returns HTTP 204. The dismissed item no longer appears in `import_queue`.

### T5 - Remaining backend panel APIs return expected shapes

Run after Tasks 4-8:

```bash
curl -s http://localhost:8001/api/datasets | python3 -m json.tool
curl -s http://localhost:8001/api/registry | python3 -m json.tool
curl -s http://localhost:8001/api/knowledge-library | python3 -m json.tool
curl -s -X POST http://localhost:8001/api/sql/execute \
  -H "Content-Type: application/json" \
  -d '{"sql": "select 1 as ok"}' | python3 -m json.tool
```

**Pass:** Each endpoint returns the documented schema without a server traceback.

---

## React Workbench Evals

### T6 - React app loads with two-column workbench layout

1. Open the Vite URL.
2. Confirm the sidebar, chat column, and panel area render.
3. Resize to a mobile-width viewport.

**Pass:** Layout remains usable with no overlapping text or controls.

### T7 - Panel navigation works for all seven panels

Open Suggestions, Study Log, Datasets, Registry, Knowledge Library, Research, and SQL.

**Pass:** Each panel loads its data or an empty state without console errors.

### T8 - Chat streams through FastAPI

Send a short Local DB message from the React chat column.

**Pass:** The response streams visibly and ends in a complete assistant message.

### T9 - Suggestions panel dismiss action works

Dismiss a pending import suggestion in the React Suggestions panel.

**Pass:** The item disappears after the mutation and refreshes from the backend.

### T10 - Knowledge Library review actions work

Approve and reject available candidate sources.

**Pass:** Actions update status and remove or restyle rows according to the UI-2 design.

### T11 - SQL panel executes a read query

Run:

```sql
select 1 as ok
```

**Pass:** The result table renders one row with `ok = 1`.

---

## Sign-off

| Eval | Result | Notes |
|------|--------|-------|
| T1 - Study log API | Pending | |
| T2 - Sessions API | Pending | |
| T3 - Suggestions API | Pending | |
| T4 - Suggestions dismiss API | Pending | |
| T5 - Remaining backend APIs | Pending | |
| T6 - React layout | Pending | |
| T7 - Panel navigation | Pending | |
| T8 - Chat streaming | Pending | |
| T9 - Suggestions dismiss UI | Pending | |
| T10 - Knowledge Library actions | Pending | |
| T11 - SQL panel | Pending | |

**Signed off:** Pending
