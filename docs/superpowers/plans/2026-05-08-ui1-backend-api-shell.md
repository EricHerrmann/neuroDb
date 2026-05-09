# UI-1: Backend API Shell — Implementation Plan

**Design source:** `docs/UI_EpochPlan.md` (Phase UI-1)
**Status:** Ready for implementation
**Prerequisite:** UI-0 (Architecture Decision) is satisfied by `docs/uiEpoch.md` — FastAPI + React confirmed as target shell, Streamlit retained during migration.

---

## Scope

Add a FastAPI application alongside the existing Streamlit app without touching or replacing any Streamlit code. The FastAPI app exposes eight named routes that the future React workbench will consume. A streaming chat SSE endpoint is included as a proof-of-concept so the streaming architecture is validated before the React shell is built.

**What UI-1 explicitly does not include:**
- No React frontend
- No Streamlit replacement or retirement
- No authentication or multi-user support
- No production deployment configuration
- No database migration (all routes read existing tables)

**Exit criteria:**
- Existing Streamlit app still starts and works
- All unit tests for the new API pass
- Manual test plan (T1–T8) passes
- No research query logic duplicated outside `research_tools.py`

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| **Create** | `src/neurodb/api/__init__.py` | UI epoch directory stub |
| **Create** | `src/neurodb/api/app.py` | `create_app(engine, ...) → FastAPI` factory |
| **Create** | `src/neurodb/api/deps.py` | FastAPI dependency providers (`get_engine`, `get_research_stores`) |
| **Create** | `src/neurodb/api/schemas/__init__.py` | Schema package |
| **Create** | `src/neurodb/api/schemas/preferences.py` | `PreferencesResponse`, `AgentModeUpdate` |
| **Create** | `src/neurodb/api/schemas/research.py` | `ResearchQuestion`, `Hypothesis`, `MetricsResponse` |
| **Create** | `src/neurodb/api/schemas/chat.py` | `ChatTurnRequest`, SSE event shapes |
| **Create** | `src/neurodb/api/routes/__init__.py` | Route package |
| **Create** | `src/neurodb/api/routes/status.py` | `GET /api/status` |
| **Create** | `src/neurodb/api/routes/preferences.py` | `GET/PUT /api/preferences` and `PUT /api/preferences/agent-mode` |
| **Create** | `src/neurodb/api/routes/research.py` | `GET /api/research/metrics`, `/questions`, `/hypotheses`; `POST /api/research/metrics/snapshot` |
| **Create** | `src/neurodb/api/routes/chat.py` | `POST /api/chat/turn` — SSE streaming via `StreamingResponse` |
| Modify | `src/neurodb/research_tools.py` | Add public `list_research_questions(engine, status)` and `list_hypotheses(engine, status)` — extract from Streamlit page |
| Modify | `pyproject.toml` | Add `fastapi>=0.115,<1.0`, `uvicorn>=0.34,<1.0` |
| **Create** | `tests/unit/test_api_status.py` | Unit tests for status route |
| **Create** | `tests/unit/test_api_preferences.py` | Unit tests for preferences GET and PUT |
| **Create** | `tests/unit/test_api_research.py` | Unit tests for metrics, questions, hypotheses routes |
| **Create** | `tests/unit/test_api_chat.py` | Unit tests for chat SSE route |
| **Create** | `docs/testsPlans/manualTestPlan_ui1_api_shell.md` | 8-eval manual plan (curl-based) |
| Modify | `docs/projectStatus.md` | Phase update: UI-1 in progress, reference table entry |

---

## Route Contracts

### `GET /api/status`

```json
{"status": "ok", "db_tables": ["research_questions", "..."], "streamlit_running": false}
```

`db_tables` is the list of ORM table names present in the DB. This confirms the engine is reachable without a full health check round-trip.

---

### `GET /api/preferences`

```json
{"agent_mode": "local_db", "relevance_threshold": 0.7}
```

Reads `agent_mode` via `load_app_preference(engine, "agent_mode", "local_db")` and `relevance_threshold` via `load_prefs()`.

---

### `PUT /api/preferences/agent-mode`

Request body: `{"mode": "neuro_research"}`

Valid values: `local_db`, `external_db`, `neuro_tutor`, `neuro_research`.

Returns `400` for unknown modes. On success:

```json
{"agent_mode": "neuro_research"}
```

Writes via `save_app_preference(engine, "agent_mode", mode)`.

---

### `GET /api/research/metrics`

Returns the dict from `get_knowledge_growth_metrics(engine, vector_store=..., knowledge_store=..., context_store=...)` with `persist=False`. Vector/knowledge/context stores are `None` when not initialized — the helper handles `None` gracefully.

---

### `POST /api/research/metrics/snapshot`

No request body. Calls `get_knowledge_growth_metrics(..., persist=True)`. Returns the same dict with an added `snapshot_id` field.

---

### `GET /api/research/questions?status=all`

Returns `list_research_questions(engine, status)` serialized to:

```json
[{"id": 1, "question": "...", "status": "open", "topic_context": "...", "created_at": "..."}]
```

Valid status values: `all`, `open`, `parked`, `converted_to_hypothesis`.

---

### `GET /api/research/hypotheses?status=all`

Returns `list_hypotheses(engine, status)` serialized to:

```json
[{"id": 1, "title": "...", "mechanism": "...", "status": "draft", "created_at": "..."}]
```

Valid status values: `all`, `draft`, `needs_evidence`, `ready_for_plan`, `archived`.

---

### `POST /api/chat/turn`

Request body:

```json
{
  "message": "What datasets are loaded?",
  "history": [],
  "agent_mode": "local_db"
}
```

Response: `Content-Type: text/event-stream`. Each SSE event carries a JSON-encoded dict:

```
data: {"type": "text_delta", "text": "I found "}\n\n
data: {"type": "tool_start", "tool_name": "query_db", "tool_input": {"sql": "..."}, "iteration": 1, "limit": 10}\n\n
data: {"type": "tool_result", "tool_name": "query_db", "result": "[{...}]"}\n\n
data: {"type": "done", "text": "The database contains...", "stop_reason": "end_turn"}\n\n
```

Error paths:
- Missing or unknown `agent_mode` → `400` before streaming starts
- `build_provider_clients()` returns empty dict (no API keys configured) → `503` before streaming starts
- Agent raises during streaming → emits `{"type": "error", "text": "..."}` event, then closes stream

Agent construction in the route:
1. `router.route(f"agent.loop.{agent_mode}")` → `(mc, model_id, max_tokens)`
2. Construct appropriate agent subclass with injected `model_client=mc`, `model=model_id`, `max_tokens=max_tokens`, `engine=engine`
3. Call `agent.chat_stream(message, history)` — yields event dicts
4. JSON-encode each event as an SSE `data:` frame

The route constructs a fresh agent per request. No server-side agent state is retained between turns.

---

## research_tools.py additions

Promote these two helpers out of `src/neurodb/ui/pages/research.py` into `research_tools.py` as public functions:

```python
def list_research_questions(engine: Engine, status: str = "all") -> list:
    """Return ResearchQuestion rows ordered by created_at desc."""
    with get_session(engine) as session:
        query = session.query(ResearchQuestion)
        if status != "all":
            query = query.filter_by(status=status)
        return query.order_by(ResearchQuestion.created_at.desc()).all()


def list_hypotheses(engine: Engine, status: str = "all") -> list:
    """Return ResearchHypothesis rows ordered by created_at desc."""
    with get_session(engine) as session:
        query = session.query(ResearchHypothesis)
        if status != "all":
            query = query.filter_by(status=status)
        return query.order_by(ResearchHypothesis.created_at.desc()).all()
```

The Streamlit research page's `_list_questions` and `_list_hypotheses` become one-line wrappers that call these public helpers, or are removed if they are private and the page imports the public versions directly.

---

## App Factory Design

```python
# src/neurodb/api/app.py
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
    app = FastAPI(title="NeuroDb API")
    app.state.engine = engine
    app.state.vector_store = vector_store
    app.state.knowledge_store = knowledge_store
    app.state.context_store = context_store
    app.state.session_manager = session_manager

    from neurodb.api.routes import status, preferences, research, chat
    app.include_router(status.router, prefix="/api")
    app.include_router(preferences.router, prefix="/api")
    app.include_router(research.router, prefix="/api/research")
    app.include_router(chat.router, prefix="/api")

    return app
```

---

## Task Checklist

### Task 0 — Manual test plan

- [ ] Create `docs/testsPlans/manualTestPlan_ui1_api_shell.md` with evals T1–T8
- [ ] Add to `docs/projectStatus.md` reference table

---

### Task 1 — Dependencies

- [ ] Add `fastapi>=0.115,<1.0` and `uvicorn>=0.34,<1.0` to `[project] dependencies` in `pyproject.toml`
- [ ] Run `uv sync` to install
- [ ] Confirm `from fastapi import FastAPI` imports cleanly

---

### Task 2 — research_tools.py list helpers (TDD)

**Write tests first in `tests/unit/test_research_tools_list.py` (or add to existing research test file):**

- `test_list_research_questions_returns_all_by_default`
- `test_list_research_questions_filters_by_status`
- `test_list_hypotheses_returns_all_by_default`
- `test_list_hypotheses_filters_by_status`

Then implement in `research_tools.py`. Then update `src/neurodb/ui/pages/research.py` to call the public helpers instead of the private `_list_questions` / `_list_hypotheses`.

---

### Task 3 — Directory stubs and schemas

- [ ] Create `src/neurodb/api/__init__.py` (UI epoch docstring)
- [ ] Create `src/neurodb/api/schemas/__init__.py`, `preferences.py`, `research.py`, `chat.py` (Pydantic models)
- [ ] Create `src/neurodb/api/routes/__init__.py`
- [ ] Create `src/neurodb/api/deps.py`

No tests needed for stubs and pure schema definitions.

---

### Task 4 — Status route (TDD)

Write `tests/unit/test_api_status.py`:

- `test_get_status_returns_ok_with_engine`

Implement `src/neurodb/api/routes/status.py` and wire into `app.py`.

---

### Task 5 — Preferences routes (TDD)

Write `tests/unit/test_api_preferences.py`:

- `test_get_preferences_returns_defaults`
- `test_get_preferences_returns_saved_agent_mode`
- `test_put_agent_mode_persists_and_returns_new_mode`
- `test_put_agent_mode_rejects_unknown_mode`

Implement `src/neurodb/api/routes/preferences.py`.

---

### Task 6 — Research routes (TDD)

Write `tests/unit/test_api_research.py`:

- `test_get_metrics_returns_count_fields`
- `test_post_snapshot_persists_and_returns_snapshot_id`
- `test_get_questions_returns_all`
- `test_get_questions_filters_by_status`
- `test_get_hypotheses_returns_all`
- `test_get_hypotheses_filters_by_status`

Implement `src/neurodb/api/routes/research.py`.

---

### Task 7 — Chat streaming route (TDD)

Write `tests/unit/test_api_chat.py`:

- `test_chat_turn_streams_done_event` — mock agent `chat_stream`; confirm SSE response contains `done` event
- `test_chat_turn_streams_tool_start_event` — mock agent with a tool call; confirm `tool_start` event in stream
- `test_chat_turn_rejects_unknown_agent_mode` — expect `400` before streaming
- `test_chat_turn_returns_503_when_no_providers` — monkeypatch `build_provider_clients` to return `{}`; expect `503`

Implement `src/neurodb/api/routes/chat.py`.

SSE encoding helper (no external dependency):

```python
def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
```

Agent construction inside the route:

```python
from neurodb.config.provider_factory import build_provider_clients
from neurodb.config.task_router import TaskRouter
from neurodb.agents.db_agent import NeuroDbAgent
from neurodb.agents.research_agent import NeuroResearchAgent
from neurodb.agents.tutor_agent import NeuroTutorAgent

_VALID_MODES = {"local_db", "external_db", "neuro_tutor", "neuro_research"}

def _build_agent(agent_mode: str, engine, vector_store, knowledge_store):
    providers = build_provider_clients()
    if not providers:
        raise RuntimeError("No provider API keys configured")
    router = TaskRouter(providers)
    route = router.route(f"agent.loop.{agent_mode}")
    if agent_mode == "neuro_research":
        return NeuroResearchAgent(
            model_client=route.model_client, model=route.model_id, max_tokens=route.max_tokens,
            engine=engine, vector_store=vector_store, knowledge_store=knowledge_store,
        )
    if agent_mode == "neuro_tutor":
        return NeuroTutorAgent(
            model_client=route.model_client, model=route.model_id,
            engine=engine, vector_store=vector_store, knowledge_store=knowledge_store,
        )
    return NeuroDbAgent(
        model_client=route.model_client, model=route.model_id, max_tokens=route.max_tokens,
        engine=engine, vector_store=vector_store, mode=agent_mode,
    )
```

---

### Task 8 — Create app factory

- [ ] Implement `src/neurodb/api/app.py` with `create_app()` as specified above
- [ ] Run full test suite: `uv run pytest tests/ -q --tb=short`
- [ ] Confirm Streamlit `app.py` still imports and runs (do not start it, just check imports)

---

### Task 9 — Manual test plan execution

Run the T1–T8 evals:
- T1: Start server with `uv run uvicorn neurodb.api.app:create_app --factory --reload`
- T2: `GET /api/status` returns `{"status": "ok", ...}`
- T3: `GET /api/preferences` returns agent_mode and relevance_threshold
- T4: `PUT /api/preferences/agent-mode` with `{"mode": "neuro_research"}` persists
- T5: `GET /api/research/metrics` returns count fields
- T6: `POST /api/research/metrics/snapshot` returns snapshot_id
- T7: `GET /api/research/questions` and `GET /api/research/hypotheses` return lists
- T8: `POST /api/chat/turn` with SSE client (`curl -N`) streams text and done event

---

### Task 10 — Docs sync

- [ ] Update `docs/projectStatus.md`:
  - Epoch Status table: UI epoch row → "UI-1 in progress"
  - Next line updated
  - Test count updated
  - Reference table entry for plan doc

---

## Execution Order

Tasks 0, 1, and 2 are independent of each other and can run in parallel.
Tasks 3–7 depend on Task 1 (FastAPI installed) and Task 2 (list helpers in research_tools).
Task 3 (stubs/schemas) has no tests and should be done before Tasks 4–7.
Tasks 4–7 are independent of each other.
Task 8 (app factory) depends on Tasks 4–7 all passing.
Task 9 (manual evals) depends on Task 8.
Task 10 after Task 9.

---

## Open Questions for Implementation

1. **API key source:** The chat route reads `ANTHROPIC_API_KEY` from environment. For the PoC this is sufficient; no route for configuring it is included in UI-1.
2. **DB concurrency:** DuckDB allows one writer at a time. If Streamlit is running and writing while the FastAPI server reads, read-only routes should be safe. The chat route (which calls agents that write telemetry) may conflict with an active Streamlit session — documented as a known constraint for the PoC.
3. **History format:** The chat route accepts history as a flat list of `{"role": "user"|"assistant", "content": "..."}` dicts, matching the Anthropic message format already used in Streamlit. Caller is responsible for maintaining history between turns.
