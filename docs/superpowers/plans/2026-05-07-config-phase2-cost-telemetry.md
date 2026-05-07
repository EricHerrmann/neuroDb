# Config Control Phase 2 — Cost Telemetry Design

**Date:** 2026-05-07
**Status:** Implementation complete — manual verification pending
**Epoch:** Config Control
**Depends on:** Config Control Phase 1 signed off 2026-05-07
**Parent plan:** `docs/superpowers/plans/2026-05-07-model-routing-impl.md`

---

## Objective

Phase 2 adds local, structured telemetry for every paid model call so model-routing decisions can be based on observed turns, tokens, model, task type, cost, and stop reason instead of assumptions.

This phase must not change model routing behavior. It only measures the current Anthropic-only system after Phase 1.

---

## Repository Findings

| Area | Current state | Phase 2 implication |
|------|---------------|---------------------|
| Agent loop | `src/neurodb/agents/base.py` owns both `_chat_inner()` and `_chat_stream_inner()` model calls. | One instrumentation point covers Local DB, External DB, Tutor, and Research agent loops. |
| Agent mode | `NeuroDbAgent` has `mode`; `NeuroTutorAgent` and `NeuroResearchAgent` do not expose mode to `BaseAgent`. | Add explicit `telemetry_mode` / `task_type` metadata to `BaseAgent` construction rather than guessing from class names. |
| Summary calls | `SessionManager._generate_summary()` and Knowledge Library `_generate_summary()` call Anthropic outside `BaseAgent`. | Add separate instrumentation at each summary call site. |
| DB sessions | Knowledge Library approval calls `_generate_summary()` while `_approve_source()` already has an open write session. | Telemetry helper must support adding rows to an existing session to avoid nested writer lock issues. |
| Schema style | ORM models live in `src/neurodb/schema.py`; `init_db()` uses `Base.metadata.create_all(engine)` and migrations for existing DB changes. | Add `ModelCallLog` ORM model and a schema migration for existing DuckDB files. |
| Failure policy | Session summary failures are swallowed; agent history rolls back on model-call failure. | Telemetry write failures must be swallowed and must never change user-facing behavior or rollback chat history. |

---

## Scope

In scope:

- Add a `ModelCallLog` ORM table.
- Add an idempotent migration for existing DB files.
- Add a small telemetry helper module.
- Instrument `BaseAgent` non-streaming and streaming model calls.
- Instrument session summary and Knowledge Library source summary calls.
- Add focused unit tests and one manual verification plan.

Out of scope:

- Provider abstraction.
- TaskRouter.
- Dynamic model selection.
- UI dashboards for telemetry.
- Quality scoring beyond raw fields available at call time.
- Changing Phase 1 model defaults.

---

## Data Model

Table: `model_call_log`

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `id` | Integer PK | Yes | Existing ORM sequence pattern. |
| `recorded_at` | String(32) | Yes | UTC ISO timestamp, matching existing schema style. |
| `task_type` | String(128) | Yes | Examples: `agent.loop.local_db`, `agent.loop.neuro_tutor`, `summary.session`. |
| `provider` | String(64) | Yes | Phase 2 always `anthropic`. |
| `model` | String(128) | Yes | Exact model ID sent to the API. |
| `mode` | String(64) | No | User-facing mode: `local_db`, `external_db`, `neuro_tutor`, `neuro_research`, or `summary`. |
| `tool_name` | String(128) | No | Primary tool name when exactly one tool is requested; first tool when multiple. |
| `tool_names_json` | Text | No | JSON array of all tool names requested by this model response. Needed because one Claude response can include multiple tool-use blocks. |
| `iteration` | Integer | No | 1-based loop iteration for agents; `1` for one-shot summaries. |
| `input_tokens` | Integer | No | From Anthropic `response.usage.input_tokens` when available. |
| `output_tokens` | Integer | No | From Anthropic `response.usage.output_tokens` when available. |
| `stop_reason` | String(64) | No | `end_turn`, `tool_use`, `max_tokens`, `terminal_tool_result`, `budget_exhausted`, or SDK-provided value. |
| `elapsed_ms` | Integer | No | Wall-clock model-call duration. |
| `estimated_cost_usd` | Float | No | Nullable when pricing for the exact model is unknown. |

Recommended indexes:

- `task_type`
- `model`
- `recorded_at`
- compound index on `task_type, model`

Rationale:

- `tool_names_json` avoids losing information from multi-tool responses.
- Token and cost fields are nullable so mocked responses and provider changes do not break instrumentation.
- Cost estimate is secondary to token capture. Tokens plus model ID are the durable facts; prices can be recalculated later when model pricing changes.

---

## Telemetry Helper

Create `src/neurodb/model_telemetry.py`.

Responsibilities:

- Extract usage fields from Anthropic responses safely.
- Extract tool-use names from response content safely.
- Estimate cost only when the model exists in the local pricing map.
- Write a `ModelCallLog` row either through an engine or through an existing SQLAlchemy session.
- Swallow telemetry write failures.

Proposed public functions:

```python
def build_model_call_log(
    *,
    task_type: str,
    provider: str,
    model: str,
    mode: str | None,
    response,
    iteration: int | None,
    elapsed_ms: int | None,
) -> ModelCallLog:
    ...

def record_model_call(engine, **kwargs) -> None:
    ...

def add_model_call_log(session, **kwargs) -> None:
    ...
```

`record_model_call(engine, ...)` opens its own short session. Use this from `BaseAgent` and `SessionManager`.

`add_model_call_log(session, ...)` attaches the row to an already-open transaction. Use this from Knowledge Library approval, where the source row is already being updated.

---

## Instrumentation Design

### BaseAgent

Add metadata to `BaseAgent.__init__()`:

```python
telemetry_mode: str | None = None
telemetry_task_type: str | None = None
```

Store:

```python
self._telemetry_mode = telemetry_mode
self._telemetry_task_type = telemetry_task_type or f"agent.loop.{telemetry_mode or 'unknown'}"
```

Subclasses pass:

| Class | Mode | Task type |
|-------|------|-----------|
| `NeuroDbAgent(mode="local_db")` | passed `mode` | `agent.loop.local_db` |
| `NeuroDbAgent(mode="external_db")` | passed `mode` | `agent.loop.external_db` |
| `NeuroTutorAgent` | `neuro_tutor` | `agent.loop.neuro_tutor` |
| `NeuroResearchAgent` | `neuro_research` | `agent.loop.neuro_research` |

In `_chat_inner()`:

- Start a timer immediately before `self._client.messages.create(...)`.
- Stop the timer immediately after the response returns.
- Record one `ModelCallLog` row for every model response.
- Use `iteration + 1`, not zero-based iteration.

In `_chat_stream_inner()`:

- Start a timer immediately before entering `self._client.messages.stream(...)`.
- Stop the timer after `stream.get_final_message()`.
- Record one `ModelCallLog` row for every final streamed message.

Failure behavior:

- If the Anthropic call raises, do not log a normal row in Phase 2. Let existing rollback behavior stand.
- If telemetry logging raises, catch and ignore it.
- If response usage is absent, log the row with null token and cost fields.

### Session Summary

In `SessionManager._generate_summary()`:

- Timer wraps the `self._client.messages.create(...)` call.
- Log `task_type = "summary.session"`.
- Log `mode = "summary"`.
- Log `iteration = 1`.
- Log `model = _SUMMARY_MODEL`.
- Use `record_model_call(engine, ...)` only if the manager has an engine available.

Design adjustment:

`SessionManager` currently receives `context_store`, `client`, and `date_provider`, but not `engine`. Phase 2 should add an optional `engine=None` constructor parameter. Existing callers/tests remain valid. Streamlit app initialization should pass the runtime engine when constructing `SessionManager`.

### Knowledge Library Summary

In `src/neurodb/ui/pages/knowledge_library.py`:

- Keep `_generate_summary()` focused on calling Anthropic and returning summary text.
- Add internal capture of response, elapsed time, and model used.
- Because `_approve_source()` already holds an open DB session, attach the log row using `add_model_call_log(session, ...)` before the transaction commits.

Implementation shape:

```python
summary, telemetry = _generate_summary(row)
row.summary = summary
if telemetry is not None:
    add_model_call_log(session, **telemetry)
```

Fallback behavior:

- If no `ANTHROPIC_API_KEY` is present, no model call happens and no telemetry row should be written.
- If the API call fails and fallback summary is returned, Phase 2 does not need a telemetry row unless a response object exists.

---

## Cost Estimation

Phase 2 should treat cost as an estimate, not a source of truth.

Recommended approach:

- Log `input_tokens`, `output_tokens`, and exact `model` first.
- Add `estimated_cost_usd` only when a local pricing map contains the model.
- Keep unknown pricing as `NULL`.
- Do not fetch pricing dynamically in Phase 2.

This avoids hardcoding a fragile external dependency into telemetry while still making the table useful. If pricing changes later, exact model IDs plus token counts allow offline recalculation.

---

## Implementation Tasks

### Task 2.0 — Manual Plan

- [x] Create `docs/testsPlans/manualTestPlan_config_phase2.md`.
- [x] Add it to `docs/projectStatus.md`.

### Task 2.1 — Schema and Migration

- [x] Add `ModelCallLog` to `src/neurodb/schema.py`.
- [x] Add indexes for `task_type`, `model`, and `task_type/model`.
- [x] Add migration 002 to create `model_call_log` for existing DB files.
- [x] Test `Base.metadata.create_all()` creates the table.
- [x] Test `init_db()` creates the table on a fresh DB.

### Task 2.2 — Telemetry Helper

- [x] Create `src/neurodb/model_telemetry.py`.
- [x] Test usage extraction with a response that has usage.
- [x] Test missing usage produces nullable token fields.
- [x] Test multi-tool content produces `tool_names_json`.
- [x] Test `record_model_call()` writes a row.
- [x] Test telemetry write failures do not raise.

### Task 2.3 — BaseAgent Instrumentation

- [x] Add telemetry metadata to `BaseAgent`.
- [x] Pass explicit telemetry mode/task type from DB, Tutor, and Research agents.
- [x] Instrument `_chat_inner()`.
- [x] Instrument `_chat_stream_inner()`.
- [x] Test non-streaming end-turn logs one row.
- [x] Test non-streaming tool-use logs the tool name and stop reason.
- [x] Test streaming final message logs one row.
- [x] Test telemetry failure does not break chat response.

### Task 2.4 — Summary Instrumentation

- [x] Add optional `engine` to `SessionManager`.
- [x] Pass engine from app/session-manager construction.
- [x] Instrument session summary calls.
- [x] Instrument Knowledge Library summary calls without opening a nested write session.
- [x] Test session summary logs one row.
- [x] Test Knowledge Library summary logs one row.
- [x] Test no API key means fallback summary and no telemetry row.

### Task 2.5 — Manual Verification

- [ ] Run automated tests.
- [ ] Start Streamlit.
- [ ] Run one Local DB query.
- [ ] Run one Neuro-Tutor prompt.
- [ ] Run one Neuro-Research prompt that uses tools.
- [ ] Clear after three turns to trigger session summary.
- [ ] Approve one Knowledge Library source to trigger source summary.
- [ ] Query `model_call_log` and verify rows by `task_type`, `model`, tokens, stop reason, and elapsed time.
- [ ] Update `docs/projectStatus.md` with final test count and sign-off when passed.

---

## Manual SQL Checks

Example verification queries:

```sql
SELECT task_type, mode, model, COUNT(*) AS calls
FROM model_call_log
GROUP BY task_type, mode, model
ORDER BY calls DESC;
```

```sql
SELECT task_type, model,
       SUM(COALESCE(input_tokens, 0)) AS input_tokens,
       SUM(COALESCE(output_tokens, 0)) AS output_tokens,
       SUM(COALESCE(estimated_cost_usd, 0)) AS estimated_cost_usd
FROM model_call_log
GROUP BY task_type, model
ORDER BY estimated_cost_usd DESC;
```

```sql
SELECT recorded_at, task_type, mode, tool_name, stop_reason, elapsed_ms
FROM model_call_log
ORDER BY recorded_at DESC
LIMIT 20;
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Telemetry logging breaks chat or summaries. | All telemetry writes catch exceptions and never alter user-facing flow. |
| Knowledge Library nested DB writes cause lock errors. | Use `add_model_call_log(session, ...)` inside the existing approval transaction. |
| Single `tool_name` field loses multi-tool responses. | Add `tool_names_json` while preserving `tool_name` as primary/first tool. |
| Pricing changes make estimates stale. | Store exact tokens/model; keep estimates nullable and recalculable. |
| Session summary has no engine reference. | Add optional `engine` to `SessionManager`; existing tests/callers continue to work. |
| Token usage absent in mocks or SDK changes. | Usage extraction is defensive and nullable. |

---

## Exit Criteria

Phase 2 is ready for sign-off when:

- `model_call_log` exists in fresh and existing DBs.
- Agent loop calls write rows for non-streaming and streaming paths.
- Session and Knowledge Library summary calls write rows.
- Telemetry write failure cannot break chat, summary, or source approval.
- Manual Streamlit verification shows rows for at least:
  - `agent.loop.local_db`
  - `agent.loop.neuro_tutor`
  - `agent.loop.neuro_research`
  - `summary.session`
  - `summary.knowledge_source`
- `docs/projectStatus.md` records the final Phase 2 test count and sign-off date.
