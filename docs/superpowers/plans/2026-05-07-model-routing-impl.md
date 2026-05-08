# Model Routing — Phased Implementation Plan

**Design source:** `docs/superpowers/plans/claudeTaskArch.md`
**Status:** Phase 1 passed — signed off 2026-05-07; Phase 2 passed — signed off 2026-05-08; Phase 3 passed — signed off 2026-05-08 with LOG-044 follow-up
**Scope decision:** Implement in four gated phases. Each phase requires its eval criteria to pass before the next phase begins. Do not work provider abstraction, config table, or TaskRouter during Phase 1–3.

---

## File Map

| Phase | Action | File | Responsibility |
|-------|--------|------|----------------|
| 1 | Modify | `src/neurodb/agents/db_agent.py` | Read `NEURODB_AGENT_MODEL`; default `claude-sonnet-4-6` |
| 1 | Modify | `src/neurodb/agents/tutor_agent.py` | Read `NEURODB_AGENT_MODEL`; default `claude-sonnet-4-6` |
| 1 | Modify | `src/neurodb/agents/research_agent.py` | Read `NEURODB_RESEARCH_MODEL`; default `claude-sonnet-4-6` |
| 1 | Modify | `src/neurodb/session_manager.py` | Read `NEURODB_SUMMARY_MODEL`; default `claude-haiku-4-5-20251001` |
| 1 | Modify | `src/neurodb/ui/pages/knowledge_library.py` | Read `NEURODB_KNOWLEDGE_SUMMARY_MODEL`; default `claude-haiku-4-5-20251001` |
| 1 | Modify | `.env` | Add four new model-routing env vars with current values |
| 1 | **Create** | `.env.example` | Template for all required env vars with placeholder values and tier labels; does not exist yet |
| 1 | Modify | `tests/unit/test_agent.py` | Tests: each agent reads its own env var; Sonnet default |
| 1 | Modify | `tests/unit/test_research_agent.py` | Test: research agent reads `NEURODB_RESEARCH_MODEL` |
| 1 | Modify | `tests/unit/test_chat_ui.py` | Test: chat init passes correct model to each agent mode |
| 2 | Modify | `src/neurodb/schema.py` | Add `ModelCallLog` ORM table |
| 2 | Create | `src/neurodb/model_telemetry.py` | Helper for safe telemetry extraction, cost estimation, and non-blocking DB writes |
| 2 | Modify | `src/neurodb/agents/base.py` | Instrument `_chat_inner` and `_chat_stream_inner` to write log rows |
| 2 | Modify | `src/neurodb/session_manager.py` | Instrument `_generate_summary()` to write log row |
| 2 | Modify | `src/neurodb/ui/pages/knowledge_library.py` | Instrument `_generate_summary()` to write log row |
| 2 | Create | `tests/unit/test_telemetry.py` | Tests: log row written per call; fields present and typed correctly |
| 3 | Modify | `src/neurodb/schema.py` | Add `HypothesisReview` ORM table |
| 3 | Modify | `src/neurodb/research_tools.py` | Add `create_hypothesis_review()` persistence helper |
| 3 | Create | `src/neurodb/hypothesis_review.py` | Premium review call: compact bundle → Opus → structured critique |
| 3 | Modify | `src/neurodb/ui/pages/research.py` | Add "Review Hypothesis" action; render linked critique |
| 3 | Modify | `.env` / `.env.example` | Add `NEURODB_PREMIUM_MODEL`; default `claude-opus-4-7` |
| 3 | Create | `tests/unit/test_hypothesis_review.py` | Tests: review call, critique persistence, no double-write |
| 4 | Create | `src/neurodb/model_client.py` | `ModelClient` ABC, `ModelResponse`, `ContentBlock` dataclasses |
| 4 | Create | `src/neurodb/providers/anthropic_client.py` | `AnthropicModelClient` — wraps current Anthropic SDK calls |
| 4 | Create | `src/neurodb/providers/openai_client.py` | `OpenAIModelClient` — OpenAI-compatible; also covers Groq |
| 4 | Create | `src/neurodb/task_router.py` | `TaskRouter` — reads config, returns `(ModelClient, model_id, max_tokens)` |
| 4 | Create | `neurodb_models.toml` | Config: tiers, providers, model IDs, eval_status, max_tokens per task |
| 4 | Modify | `src/neurodb/agents/base.py` | Refactor loop to call `ModelClient` instead of `self._client.messages.*` |
| 4 | Create | `tests/unit/test_model_client.py` | Tests: normalized response contract; tool schema translation |
| 4 | Create | `tests/unit/test_task_router.py` | Tests: config loading; task → tier → client routing |
| All | Modify | `docs/projectStatus.md` | Sync phase status and test count after each phase |

---

## Task Checklist

### Phase 1 — Per-Agent Env Vars

**Goal:** Stop using Opus as the universal default. No architectural change.

#### Task 1.0 — Manual test plan

- [x] Create `docs/testsPlans/manualTestPlan_config_phase1.md` with evals for all workflows affected by this phase
- [x] Add plan to `docs/projectStatus.md` reference table

#### Task 1.1 — Agent model env vars

- [x] In `db_agent.py`: replace `os.environ.get("NEURODB_MODEL", _DEFAULT_MODEL)` with `os.environ.get("NEURODB_AGENT_MODEL", "claude-sonnet-4-6")` at module level
- [x] In `tutor_agent.py`: same substitution for `NEURODB_AGENT_MODEL`
- [x] In `research_agent.py`: replace with `os.environ.get("NEURODB_RESEARCH_MODEL", "claude-sonnet-4-6")`
- [x] Remove any remaining references to global `NEURODB_MODEL` in agent modules (keep it only in `base.py` as the fallback constant, or remove entirely)
- [x] Write failing test: `NeuroDbAgent` reads `NEURODB_AGENT_MODEL`, not `NEURODB_MODEL`
- [x] Write failing test: `NeuroTutorAgent` reads `NEURODB_AGENT_MODEL`
- [x] Write failing test: `NeuroResearchAgent` reads `NEURODB_RESEARCH_MODEL`
- [x] Run tests — confirm red
- [x] Implement changes — confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 1.2 — Summary model env vars

- [x] In `session_manager.py`: replace `_SUMMARY_MODEL = os.environ.get("NEURODB_MODEL", ...)` with `_SUMMARY_MODEL = os.environ.get("NEURODB_SUMMARY_MODEL", "claude-haiku-4-5-20251001")`
- [x] In `knowledge_library.py` `_generate_summary()`: replace inline `os.environ.get("NEURODB_MODEL", ...)` with `os.environ.get("NEURODB_KNOWLEDGE_SUMMARY_MODEL", "claude-haiku-4-5-20251001")`
- [x] Write failing test: session summary uses `NEURODB_SUMMARY_MODEL`
- [x] Write failing test: Knowledge Library summary uses `NEURODB_KNOWLEDGE_SUMMARY_MODEL`
- [x] Run tests — confirm red
- [x] Implement changes — confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 1.3 — Env file and chat wiring

**`.env` vs `.env.example`:** `.env` holds real API keys and is gitignored (line 130 of `.gitignore`). `.env.example` is a committed template showing every required env var with placeholder values — its purpose is to tell contributors what keys they need without exposing real credentials. `.env.example` does not currently exist and must be created.

- [x] Add all four new model-routing vars to `.env` with current values and tier comments
- [x] **Create** `.env.example` with placeholder values for all env vars (model keys, tool keys, and the four new model-routing vars); include tier labels as comments
- [x] Verify `chat.py` agent construction passes the model read from the agent's own env var (should follow automatically from Task 1.1)
- [x] Run full `uv run pytest tests/ -q --tb=no`
- [x] Update `docs/projectStatus.md` with new test count

#### Task 1.4 — Phase 1 evals (manual)

Run against the live Streamlit app with new env vars active. Record pass/fail for each.

| Eval | Model | Pass criteria |
|------|-------|---------------|
| Local DB query | Sonnet | Correct SQL, correct result, no fabricated IDs |
| External DB discovery | Sonnet | Valid source calls, grounded candidates |
| Neuro-Tutor explanation | Sonnet | Clear, accurate, Knowledge Library referenced where relevant |
| Session summary on Clear | Haiku | Correct date/topic/concepts, no invented datasets |
| Knowledge Library source summary | Haiku | Useful structured summary, no invented DOI or source claims |

- [x] All Phase 1 evals pass before proceeding to Phase 2

---

### Phase 2 — Cost Telemetry

**Goal:** Measure actual iteration and token distribution. Gate on data before making stronger tier claims.
**Detailed design:** `docs/superpowers/plans/2026-05-07-config-phase2-cost-telemetry.md`

#### Task 2.0 — Manual test plan

- [x] Create `docs/testsPlans/manualTestPlan_config_phase2.md` with evals covering: telemetry rows written per agent call, telemetry rows written per summary call, all fields present and correctly typed
- [x] Add plan to `docs/projectStatus.md` reference table

#### Task 2.1 — Schema

- [x] Add `ModelCallLog` ORM table to `src/neurodb/schema.py` with columns: `id`, `recorded_at`, `task_type`, `provider`, `model`, `mode`, `tool_name`, `tool_names_json`, `iteration`, `input_tokens`, `output_tokens`, `stop_reason`, `elapsed_ms`, `estimated_cost_usd`
- [x] Add indexes for `task_type`, `model`, `recorded_at`, and compound `task_type/model`
- [x] Add migration 002 to create `model_call_log` for existing DB files
- [x] Write failing schema test: `ModelCallLog` table created by `init_db`
- [x] Run test — confirm red; implement; confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 2.2 — Telemetry helper

- [x] Create `src/neurodb/model_telemetry.py`
- [x] Implement defensive usage extraction from Anthropic responses
- [x] Implement tool-name extraction, including multi-tool responses into `tool_names_json`
- [x] Implement nullable cost estimation from exact model ID and token counts
- [x] Implement `record_model_call(engine, ...)` for standalone writes
- [x] Implement `add_model_call_log(session, ...)` for existing transactions
- [x] Ensure telemetry write failures are swallowed
- [x] Write tests for usage extraction, missing usage, multi-tool extraction, row write, and write-failure safety
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 2.3 — Agent loop instrumentation

- [x] In `base.py` `_chat_inner`: after each `messages.create()` response, write one `ModelCallLog` row
- [x] In `base.py` `_chat_stream_inner`: after each `stream.get_final_message()`, write one `ModelCallLog` row
- [x] Add explicit telemetry mode/task type metadata to `BaseAgent` construction
- [x] Pass `local_db` / `external_db` from `NeuroDbAgent`, `neuro_tutor` from `NeuroTutorAgent`, and `neuro_research` from `NeuroResearchAgent`
- [x] Pass `engine` into the log write through `record_model_call`; do not raise if log write fails
- [x] Log `task_type` as `"agent.loop.<mode>"`
- [x] Write failing test: `_chat_inner` writes one log row per iteration
- [x] Write failing test: `_chat_stream_inner` writes one log row per iteration
- [x] Write failing test: telemetry write failure does not break chat response
- [x] Run tests — confirm red; implement; confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 2.4 — Summary instrumentation

- [x] Add optional `engine=None` to `SessionManager` so session-summary telemetry can write rows when available
- [x] In `session_manager.py` `_generate_summary()`: write one `ModelCallLog` row with `task_type = "summary.session"` and `mode = "summary"`
- [x] In `knowledge_library.py`: attach one `ModelCallLog` row with `task_type = "summary.knowledge_source"` using the existing approval DB session
- [x] Write failing tests for both
- [x] Write failing test: Knowledge Library fallback without API key writes no telemetry row
- [x] Run tests — confirm red; implement; confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 2.5 — Verify telemetry

- [x] Start Streamlit, run a Local DB query, run a Tutor prompt, run a research prompt, clear session, approve one Knowledge Library source
- [x] Query `model_call_log` directly: confirm rows present with correct `task_type`, `mode`, `model`, `input_tokens`, `output_tokens`, `stop_reason`, `elapsed_ms`
- [x] Update `docs/projectStatus.md` with new test count
- [x] All Phase 2 evals pass before proceeding to Phase 3

---

### Phase 3 — Research Synthesis Split

**Goal:** Reserve a bounded Opus call for hypothesis review; research loop stays on Sonnet.

#### Task 3.0 — Manual test plan

- [x] Create `docs/testsPlans/manualTestPlan_config_phase3.md` with evals covering: hypothesis draft on Sonnet, hypothesis review on Opus, no double persistence, telemetry rows for both calls
- [x] Add plan to `docs/projectStatus.md` reference table

#### Task 3.1 — HypothesisReview schema

- [x] Add `HypothesisReview` ORM table to `src/neurodb/schema.py` with columns: `id`, `hypothesis_id` (FK to `ResearchHypothesis`), `created_at`, `model`, `critique_text`, `unsupported_claims` (JSON array), `missing_confounds` (JSON array), `suggested_revisions` (text), `status` (e.g. `"pending"`, `"accepted"`, `"dismissed"`)
- [x] Write failing schema test
- [x] Run test — confirm red; implement; confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 3.2 — Premium env var and review helper

- [x] Add `NEURODB_PREMIUM_MODEL = os.environ.get("NEURODB_PREMIUM_MODEL", "claude-opus-4-7")` to `hypothesis_review.py`
- [x] Add `NEURODB_PREMIUM_MODEL` to `.env` and `.env.example`
- [x] Add review persistence helper to `src/neurodb/research_tools.py`; provider call and structured parsing live in `hypothesis_review.py`
- [x] Write failing tests: review persisted; hypothesis row unchanged; no second `ResearchHypothesis` row created
- [x] Run tests — confirm red; implement; confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 3.3 — Hypothesis review logic

- [x] Create `src/neurodb/hypothesis_review.py`
- [x] Implement `run_hypothesis_review(hypothesis_id, engine, client, model)`: builds a compact prompt from hypothesis fields + evidence, calls `client.messages.create()` with `NEURODB_PREMIUM_MODEL`, parses response into critique fields, calls `create_hypothesis_review()`
- [x] System prompt must clearly mark the output as a critique of a draft, not a confirmed finding
- [x] Write failing tests: output contains `unsupported_claims`, `missing_confounds`, `suggested_revisions`; model used is `NEURODB_PREMIUM_MODEL` not the loop model
- [x] Run tests — confirm red; implement; confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 3.4 — Research workspace UI

- [x] In `src/neurodb/ui/pages/research.py`: add "Review Hypothesis" button next to each draft hypothesis in the hypotheses list
- [x] On click: call `run_hypothesis_review()`, refresh the hypothesis detail panel to show critique
- [x] Render critique sections: unsupported claims, missing confounds, suggested revisions
- [x] Add "Accept revisions" and "Dismiss review" actions that update the `HypothesisReview.status` field
- [x] Write failing structural test: Research tab renders review action when hypotheses exist
- [x] Run tests — confirm red; implement; confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`
- [x] Update `docs/projectStatus.md` with new test count

#### Task 3.5 — Phase 3 evals (manual)

| Eval | Model | Pass criteria |
|------|-------|---------------|
| Research loop drafts hypothesis | Sonnet | Evidence, predictions, datasets, confounds, limitations present; `status = "draft"` |
| "Review Hypothesis" action | Opus | Critique rendered; at least one unsupported claim or missing confound identified |
| No double persistence | Both | `ResearchHypothesis` row count unchanged after review; only `HypothesisReview` row added |
| Telemetry | Both | Log rows for loop (Sonnet) and review call (Opus) both present with correct `model` field |

- [x] All Phase 3 evals pass before proceeding to Phase 4

**Phase 3 sign-off note:** T2 and T3 passed with a follow-up issue: the premium review response was not structured JSON and required manual revision. LOG-044 tracks hardening the review prompt/parser so future review output is directly evaluable as structured JSON.

---

### Phase 4 — Provider Abstraction + Config-Driven Model Table

**Goal:** Decouple `BaseAgent` from the Anthropic SDK; make model ID updates a config change; add OpenAI/Groq support.

#### Task 4.0 — Manual test plan

- [ ] Create `docs/testsPlans/manualTestPlan_config_phase4.md` with evals covering: agent loop against OpenAI model, research loop against OpenAI model, Phase 1 evals re-run against OpenAI provider for parity
- [ ] Add plan to `docs/projectStatus.md` reference table

#### Task 4.1 — ModelClient interface and normalized types

- [ ] Create `src/neurodb/model_client.py`
- [ ] Define `ContentBlock` dataclass: `type`, `text`, `tool_name`, `tool_use_id`, `tool_input`
- [ ] Define `ModelResponse` dataclass: `stop_reason`, `content: list[ContentBlock]`
- [ ] Define `ModelStream` protocol: iterable of text-delta dicts + `get_final_message() -> ModelResponse`
- [ ] Define `ModelClient` ABC: `create_message(...)`, `stream_message(...)`, `format_tool(...)`, `format_tool_result(...)`
- [ ] Write failing tests: `ModelResponse` and `ContentBlock` construct correctly; ABC cannot be instantiated
- [ ] Run tests — confirm red; implement; confirm green

#### Task 4.2 — AnthropicModelClient

- [ ] Create `src/neurodb/providers/anthropic_client.py`
- [ ] Implement `AnthropicModelClient(ModelClient)`: wraps `anthropic.Anthropic` SDK
- [ ] `create_message()`: calls `client.messages.create()`, maps response to `ModelResponse`
- [ ] `stream_message()`: calls `client.messages.stream()`, wraps in `ModelStream`
- [ ] `format_tool()`: returns tool dict unchanged (Anthropic already uses `input_schema`)
- [ ] `format_tool_result()`: returns Anthropic `tool_result` message dict
- [ ] Write failing tests: `create_message` returns `ModelResponse`; `stop_reason` values map correctly; tool schema passes through unchanged
- [ ] Run tests — confirm red; implement; confirm green
- [ ] Run full `uv run pytest tests/ -q --tb=no`

#### Task 4.3 — BaseAgent refactor

- [ ] Refactor `_chat_inner` in `base.py`: replace `self._client.messages.create()` with `self._model_client.create_message()`; replace `block.type`, `block.name`, `block.input`, `block.id` with normalized `ContentBlock` attributes
- [ ] Refactor `_chat_stream_inner`: replace `self._client.messages.stream()` with `self._model_client.stream_message()`
- [ ] `BaseAgent.__init__` accepts `model_client: ModelClient` instead of (or alongside) `client`
- [ ] All existing tests must pass using `AnthropicModelClient` as the adapter
- [ ] Run full `uv run pytest tests/ -q --tb=no` — must stay green; no new failures

#### Task 4.4 — Config-driven model table

- [ ] Create `neurodb_models.toml` at repo root with tier/provider/model/eval_status/max_tokens entries from the design
- [ ] Create `src/neurodb/model_config.py`: `load_model_config()` reads the TOML; `get_model_for_task(task_type)` returns `(provider, model_id, max_tokens)`
- [ ] Write failing tests: config loads without error; `get_model_for_task("summary.session")` returns economy-tier Haiku entry; unknown task type raises a clear error
- [ ] Run tests — confirm red; implement; confirm green
- [ ] Run full `uv run pytest tests/ -q --tb=no`

#### Task 4.5 — TaskRouter

- [ ] Create `src/neurodb/task_router.py`
- [ ] Implement `TaskRouter`: holds a map of provider name → `ModelClient` instance; `route(task_type)` calls `get_model_for_task()` then returns the matching client, model ID, and max_tokens
- [ ] Wire `TaskRouter` into agent construction in `chat.py` — agents receive a routed client for their task type
- [ ] Write failing tests: `route("agent.loop.research")` returns standard-tier client; `route("research.hypothesis_review")` returns premium-tier client
- [ ] Run tests — confirm red; implement; confirm green
- [ ] Run full `uv run pytest tests/ -q --tb=no`

#### Task 4.6 — OpenAIModelClient

- [ ] Create `src/neurodb/providers/openai_client.py`
- [ ] Implement `OpenAIModelClient(ModelClient)`: wraps `openai.OpenAI` SDK
- [ ] `format_tool()`: translate `input_schema` → OpenAI `parameters` format
- [ ] `format_tool_result()`: return OpenAI `tool` role message dict
- [ ] `create_message()`: call `client.chat.completions.create()` with `tools=`; map choice to `ModelResponse`
- [ ] `stream_message()`: call with `stream=True`; wrap in `ModelStream`
- [ ] Note: Groq uses the same OpenAI-compatible API — `OpenAIModelClient` with `base_url` override covers both
- [ ] Write failing tests: tool schema translates correctly from Anthropic format; `stop_reason` values normalized to `"end_turn"` / `"tool_use"` / `"max_tokens"`
- [ ] Run Phase 1 evals against OpenAI models to validate provider parity
- [ ] Run full `uv run pytest tests/ -q --tb=no`
- [ ] Update `docs/projectStatus.md` with final test count

---

## Execution Order

1. Phase 1 before Phase 2 — env vars must be stable before telemetry labels task types
2. Phase 2 before Phase 3 — telemetry data validates the research loop iteration profile before the synthesis split is designed as final
3. Phase 3 before Phase 4 — synthesis split is the highest-value dynamic routing case; it should be working and tested before the abstraction layer wraps it
4. Phase 4 tasks in order: interface → Anthropic adapter → BaseAgent refactor → config → router → OpenAI adapter

---

## Stop Criteria

- If Phase 1 evals show Sonnet produces fabricated dataset IDs or incorrect SQL that Opus did not, stop and escalate the affected task type to standard → premium before proceeding
- If Phase 2 telemetry shows the research loop is already spending most tokens on the hypothesis step (not orchestration), revisit the Phase 3 design before implementing — the split may be less valuable than modeled
- If `BaseAgent` refactor in Task 4.3 breaks more than three existing tests, stop and investigate the abstraction boundary before continuing
- Do not add Gemini provider, automated model promotion, or model cost dashboard UI during any phase of this plan
- Do not change the `draft_hypothesis` tool schema during Phase 3 — the two-step draft/review design explicitly avoids that
