# Manual Test Plan — UI-1: Backend API Shell

**Epoch scope:** UI — tests the FastAPI backend shell added in UI-1. Streamlit is not tested here; it is verified still functional as a side condition of T1.

**Phase:** UI-1
**Design source:** `docs/superpowers/plans/2026-05-08-ui1-backend-api-shell.md`
**Status:** In progress — 2026-05-11

---

## Prerequisites

1. **Automated tests pass.** Run the full suite and confirm no new failures:
   ```bash
   uv run pytest tests/ -q
   ```
   Pass: output ends with a green summary line (e.g. `408 passed, 9 failed`) where every failure is already tracked in `docs/testLog.md`. Do not proceed if there are new failures.

2. `uv run streamlit run src/neurodb/ui/app.py` starts without error (verify before starting the API server, then stop it)
3. `uv run uvicorn neurodb.api.app:app_factory --factory --port 8001` starts without error
4. `.env` present with `ANTHROPIC_API_KEY` set
5. At least one `ResearchQuestion` and one `ResearchHypothesis` row in the DB (created via the Streamlit research agent or seeded manually)

---

## Test Evals

### T1 — Streamlit still runs after API shell is added

**Goal:** Confirm the new `src/neurodb/api/` package does not break the existing Streamlit entry point.

**Steps:**
1. Stop the FastAPI server if running.
2. Run `uv run streamlit run src/neurodb/ui/app.py`.
3. Observe the browser opens and the app loads without import errors.

**Pass:** App page renders; no error banner or import traceback in the terminal.

**Fail:** Any import error, `ModuleNotFoundError`, or crash on startup.

---

### T2 — `GET /api/status` returns ok

**Steps:**
```bash
curl -s http://localhost:8001/api/status | python3 -m json.tool
```

**Pass:** Response contains `{"status": "ok", ...}` with a `db_tables` list that includes at least `research_questions` and `research_hypotheses`.

**Fail:** Non-200 response, missing `status` field, or empty `db_tables`.

---

### T3 — `GET /api/preferences` returns agent_mode and threshold

**Steps:**
```bash
curl -s http://localhost:8001/api/preferences | python3 -m json.tool
```

**Pass:** Response contains `agent_mode` (a non-empty string) and `relevance_threshold` (a number).

**Fail:** Missing either field; non-200 response.

---

### T4 — `PUT /api/preferences/agent-mode` persists the new mode

**Steps:**
```bash
# Set to neuro_research
curl -s -X PUT http://localhost:8001/api/preferences/agent-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "neuro_research"}' | python3 -m json.tool

# Confirm it was saved
curl -s http://localhost:8001/api/preferences | python3 -m json.tool
```

**Pass:**
- PUT returns `{"agent_mode": "neuro_research"}`.
- Subsequent GET returns `"agent_mode": "neuro_research"`.

**Fail:** PUT returns non-200; GET still shows old mode.

**Cleanup:** Reset to `local_db` after the test:
```bash
curl -s -X PUT http://localhost:8001/api/preferences/agent-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "local_db"}'
```

---

### T5 — `GET /api/research/metrics` returns count fields

**Steps:**
```bash
curl -s http://localhost:8001/api/research/metrics | python3 -m json.tool
```

**Pass:** Response contains all of: `snapshot_at`, `approved_sources_count`, `research_questions_count`, `research_hypotheses_count`, `chat_sessions_count`. All values are numbers or null (not missing keys).

**Fail:** Missing any required count field; non-200 response.

---

### T6 — `POST /api/research/metrics/snapshot` persists and returns snapshot_id

**Steps:**
```bash
curl -s -X POST http://localhost:8001/api/research/metrics/snapshot | python3 -m json.tool
```

**Pass:** Response contains `snapshot_id` (a positive integer). Re-running returns a different (higher) `snapshot_id`.

**Fail:** Missing `snapshot_id`; non-200 response; repeated calls return the same `snapshot_id`.

---

### T7 — `GET /api/research/questions` and `GET /api/research/hypotheses` return lists

**Steps:**
```bash
curl -s "http://localhost:8001/api/research/questions" | python3 -m json.tool
curl -s "http://localhost:8001/api/research/hypotheses" | python3 -m json.tool
curl -s "http://localhost:8001/api/research/questions?status=open" | python3 -m json.tool
```

**Pass:**
- All three return JSON arrays (may be empty if no rows).
- Each item in the questions array has: `id`, `question`, `status`, `topic_context`, `created_at`.
- Each item in the hypotheses array has: `id`, `title`, `mechanism`, `status`, `created_at`.
- Status filter: `?status=open` returns only rows where `status == "open"`.

**Fail:** Non-array response; missing required fields; status filter ignored.

---

### T8 — `POST /api/chat/turn` streams SSE events

**Steps:**
```bash
curl -N -s -X POST http://localhost:8001/api/chat/turn \
  -H "Content-Type: application/json" \
  -d '{"message": "How many datasets are loaded?", "history": [], "agent_mode": "local_db"}'
```

**Pass:**
- Response is a stream of `data: {...}` lines.
- At least one `{"type": "text_delta", ...}` event appears.
- Stream ends with a `{"type": "done", ...}` event containing a non-empty `text` field.
- No Python traceback in the server terminal.

**Fail:** Non-200 before streaming; no `done` event; `{"type": "error", ...}` event in the stream; server crash.

**Variant — unknown agent mode returns 400 before streaming:**
```bash
curl -s -X POST http://localhost:8001/api/chat/turn \
  -H "Content-Type: application/json" \
  -d '{"message": "hi", "history": [], "agent_mode": "not_a_real_mode"}'
```

Pass: HTTP 400 response, no stream opened.

---

## Sign-off

| Eval | Result | Notes |
|------|--------|-------|
| T1 — Streamlit still runs | | |
| T2 — GET /api/status | | |
| T3 — GET /api/preferences | | |
| T4 — PUT /api/preferences/agent-mode | | |
| T5 — GET /api/research/metrics | | |
| T6 — POST /api/research/metrics/snapshot | | |
| T7 — GET questions and hypotheses | | |
| T8 — POST /api/chat/turn SSE stream | | |

**Signed off:** —
