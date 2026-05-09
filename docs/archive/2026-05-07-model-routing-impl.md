# Model Routing — Phased Implementation Plan

**Design source:** `docs/superpowers/plans/claudeTaskArch.md`
**Status:** Phase 1 passed — signed off 2026-05-07; Phase 2 passed — signed off 2026-05-08; Phase 3 passed — signed off 2026-05-08 with LOG-044 follow-up; Phase 4 manual evals pending (T1–T7); Phase 5A/5B complete — 398 tests; Phase 6 planned — constructor fallback chain, system warnings table, CLI surface, TOML tuning section (iteration limits + relevance threshold), model API error logging
**Scope decision:** Implement in gated phases. Each phase requires its eval criteria to pass before the next phase begins. Do not work provider abstraction, config table, or TaskRouter during Phase 1–3.

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
| 6 | Modify | `src/neurodb/agents/base.py` | Add `_resolve_model()` with 4-step fallback chain; emit `logging.warning()` on steps 3–4; read iteration limit from TOML tuning section |
| 6 | Modify | `src/neurodb/agents/db_agent.py` | Remove module-level `_MODEL = os.environ.get(...)`; read `max_tool_iterations` from TOML |
| 6 | Modify | `src/neurodb/agents/tutor_agent.py` | Remove module-level `_MODEL = os.environ.get(...)`; read `max_tool_iterations` from TOML |
| 6 | Modify | `src/neurodb/agents/research_agent.py` | Remove module-level `_MODEL = os.environ.get(...)`; remove `NEURODB_RESEARCH_MAX_TOOL_ITERATIONS` env var; read from TOML |
| 6 | Modify | `src/neurodb/session_manager.py` | Remove module-level `_SUMMARY_MODEL`; read `session_relevance_threshold` from TOML tuning section |
| 6 | Modify | `src/neurodb/research/hypothesis_review.py` | Remove module-level `NEURODB_PREMIUM_MODEL = os.environ.get(...)` |
| 6 | Modify | `src/neurodb/ui/pages/knowledge_library.py` | Remove legacy env var read; rely on constructor-level resolution |
| 6 | Modify | `neurodb_models.toml` | Add `[tuning]` section: `max_tool_iterations` per agent type, `session_relevance_threshold` |
| 6 | Modify | `src/neurodb/config/model_config.py` | Add `get_tuning_value(key)` helper to read `[tuning]` section |
| 6 | Modify | `src/neurodb/schema.py` | Add `SystemWarning` ORM table |
| 6 | Modify | `src/neurodb/model_telemetry.py` | Add `record_system_warning()` helper |
| 6 | Create | `src/neurodb/cli/warnings.py` | CLI query: print recent system warnings from DB |
| 6 | Modify | `.env.example` | Comment out legacy model vars and `NEURODB_RESEARCH_MAX_TOOL_ITERATIONS`; add transition note |
| 6 | Modify | `src/neurodb/agents/base.py` | Catch API exceptions in `chat()` / `chat_stream()`; emit `logging.error()` + write `system_warnings` row before re-raising |
| 6 | Create | `tests/unit/test_system_warnings.py` | Tests: warning row written on fallback; API error row written on exception; fields correct |
| 6 | Create | `tests/unit/test_tuning_config.py` | Tests: `get_tuning_value` returns correct defaults; missing key raises clearly |
| 6 | Create | `docs/testsPlans/manualTestPlan_config_phase6.md` | Manual evals: nominal path, fallback logging, API error logging, CLI output, iteration limits respected |

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

- [x] Create `docs/testsPlans/manualTestPlan_config_phase4.md` with evals covering: agent loop against OpenAI model, research loop against OpenAI model, Phase 1 evals re-run against OpenAI provider for parity
- [x] Add plan to `docs/projectStatus.md` reference table

#### Task 4.1 — ModelClient interface and normalized types

- [x] Create `src/neurodb/model_client.py`
- [x] Define `ContentBlock` dataclass: `type`, `text`, `tool_name`, `tool_use_id`, `tool_input`
- [x] Define `ModelResponse` dataclass: `stop_reason`, `content: list[ContentBlock]`, `input_tokens`, `output_tokens`
- [x] Define `ModelStream` protocol: iterable of text-delta dicts + `get_final_message() -> ModelResponse`
- [x] Define `ModelClient` ABC: `create_message(...)`, `stream_message(...)`, `format_tool(...)`, `format_tool_result(...)`
- [x] Write failing tests: `ModelResponse` and `ContentBlock` construct correctly; ABC cannot be instantiated
- [x] Run tests — confirm red; implement; confirm green

#### Task 4.2 — AnthropicModelClient

- [x] Create `src/neurodb/providers/anthropic_client.py`
- [x] Implement `AnthropicModelClient(ModelClient)`: wraps `anthropic.Anthropic` SDK
- [x] `create_message()`: calls `client.messages.create()`, maps response to `ModelResponse`
- [x] `stream_message()`: calls `client.messages.stream()`, wraps in `_AnthropicStream` (ModelStream)
- [x] `format_tool()`: returns tool dict unchanged (Anthropic already uses `input_schema`)
- [x] `format_tool_result()`: returns Anthropic `tool_result` message dict
- [x] Write failing tests: `create_message` returns `ModelResponse`; `stop_reason` values map correctly; tool schema passes through unchanged
- [x] Run tests — confirm red; implement; confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 4.3 — BaseAgent refactor

- [x] Refactor `_chat_inner` in `base.py`: replace `self._client.messages.create()` with `self._model_client.create_message()`; replace `block.type`, `block.name`, `block.input`, `block.id` with normalized `ContentBlock` attributes
- [x] Refactor `_chat_stream_inner`: replace `self._client.messages.stream()` with `self._model_client.stream_message()`
- [x] `BaseAgent.__init__` accepts `model_client: ModelClient` instead of (or alongside) `client`
- [x] All existing tests pass using `AnthropicModelClient` as the adapter
- [x] Run full `uv run pytest tests/ -q --tb=no` — no new failures (379→382 after new tests added)

#### Task 4.4 — Config-driven model table

- [x] Create `neurodb_models.toml` at repo root with tier/provider/model/eval_status/max_tokens entries from the design
- [x] Create `src/neurodb/model_config.py`: `load_model_config()` reads the TOML; `get_model_for_task(task_type)` returns `(provider, model_id, max_tokens)`
- [x] Write failing tests: config loads without error; `get_model_for_task("summary.session")` returns economy-tier Haiku entry; unknown task type raises a clear error
- [x] Run tests — confirm red; implement; confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 4.5 — TaskRouter

- [x] Create `src/neurodb/task_router.py`
- [x] Implement `TaskRouter`: holds a map of provider name → `ModelClient` instance; `route(task_type)` calls `get_model_for_task()` then returns the matching client, model ID, and max_tokens
- [x] Wire `TaskRouter` into agent construction in `chat.py` — agents receive a routed client for their task type
- [x] Write failing tests: `route("agent.loop.research")` returns standard-tier client; `route("research.hypothesis_review")` returns premium-tier client
- [x] Run tests — confirm red; implement; confirm green
- [x] Run full `uv run pytest tests/ -q --tb=no`

#### Task 4.6 — OpenAIModelClient

- [x] Create `src/neurodb/providers/openai_client.py`
- [x] Implement `OpenAIModelClient(ModelClient)`: wraps `openai.OpenAI` SDK
- [x] `format_tool()`: translate `input_schema` → OpenAI `parameters` format
- [x] `format_tool_result()`: return OpenAI `tool` role message dict
- [x] `create_message()`: call `client.chat.completions.create()` with `tools=`; map choice to `ModelResponse`
- [x] `stream_message()`: call with `stream=True`; wrap in `_OpenAIStream`
- [x] Note: Groq uses the same OpenAI-compatible API — `OpenAIModelClient` with `base_url` override covers both
- [x] Write failing tests: tool schema translates correctly from Anthropic format; `stop_reason` values normalized to `"end_turn"` / `"tool_use"` / `"max_tokens"`
- [ ] Run Phase 1 evals against OpenAI models to validate provider parity (manual eval — pending T5/T6)
- [x] Run full `uv run pytest tests/ -q --tb=no`
- [x] Update `docs/projectStatus.md` with final test count (382)

#### Task 4.7 — Provider selection wiring fix

**Status:** Implemented — 389 automated tests passing. Manual OpenAI parity evals T5/T6 remain pending.

**Original problem:** Phase 4 had provider adapters and a `TaskRouter`, but provider selection was not actually runnable from the app. `chat.py` registered only Anthropic with `TaskRouter`, `neurodb_models.toml` contained only Anthropic provider entries, `NEURODB_AGENT_MODEL_PROVIDER=openai` was not read anywhere, and agent telemetry still wrote `provider="anthropic"` directly. This blocked manual evals T5/T6.

**Design goal:** Make provider selection config-driven, with a small env override for manual evals, while keeping Anthropic as the default MVP provider.

**Selection precedence:**

1. Tier-specific environment override for manual tests:
   - `NEURODB_ECONOMY_PROVIDER`
   - `NEURODB_STANDARD_PROVIDER`
   - `NEURODB_PREMIUM_PROVIDER`
2. `default_provider` from `neurodb_models.toml`

Do not add per-agent provider env vars such as `NEURODB_AGENT_MODEL_PROVIDER`; provider selection should follow task type → tier → provider so it remains compatible with task-based routing.

**Config change:**

Add provider entries for OpenAI to each tier in `neurodb_models.toml`, while leaving Anthropic as the default provider:

```toml
[tiers.standard.providers.openai]
model = "gpt-5-mini"
eval_status = "candidate"
last_verified_at = ""
```

The exact OpenAI model IDs should be treated as config values, not source-code constants. If an OpenAI model is not verified for a tier, keep `eval_status = "candidate"` until manual evals pass.

**Routing shape:**

Replace the current `(ModelClient, model_id, max_tokens)` route tuple with a named route object:

```python
@dataclass(frozen=True)
class ModelRoute:
    task_type: str
    tier: str
    provider: str
    model_client: ModelClient
    model_id: str
    max_tokens: int
```

`TaskRouter.route(task_type)` should return `ModelRoute`. This keeps provider identity attached to the selected model and avoids inferring provider from the adapter class.

**Provider factory:**

Add a small provider factory in `src/neurodb/config/provider_factory.py`:

- If `ANTHROPIC_API_KEY` exists, construct `AnthropicModelClient`.
- If `OPENAI_API_KEY` exists, construct `OpenAIModelClient`.
- If `GROQ_API_KEY` exists, construct `OpenAIModelClient` with Groq `base_url`.
- Return `dict[str, ModelClient]`.

The app should then build `TaskRouter(build_provider_clients())` instead of manually constructing only Anthropic in `chat.py`.

**Telemetry change:**

`BaseAgent.__init__` should accept `model_provider: str`. `chat.py` should pass `route.provider` when constructing each agent. `_record_model_call()` should write `provider=self._model_provider` instead of `provider="anthropic"`.

This is deliberately route-owned rather than client-owned because `OpenAIModelClient` may represent either OpenAI or Groq depending on SDK configuration.

**Call-site changes:**

- In `chat.py`, call `route = router.route(task_type)`.
- Pass:
  - `model_client=route.model_client`
  - `model=route.model_id`
  - `max_tokens=route.max_tokens`
  - `model_provider=route.provider`
- For hypothesis review, route `research.hypothesis_review` and pass both `model_client=route.model_client` and `model=route.model_id`; `run_hypothesis_review()` should record `provider=route.provider`.

**Manual eval path after implementation:**

To run T5 without editing source code:

```bash
NEURODB_STANDARD_PROVIDER=openai uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

Then run the existing T5 telemetry query and confirm the newest `agent.loop.local_db` row has `provider=openai`.

**Implemented test coverage:**

- [x] `get_model_for_task()` honors `NEURODB_STANDARD_PROVIDER=openai` when the standard tier has an OpenAI provider entry.
- [x] Unknown provider override raises a clear `KeyError` naming the missing provider and tier.
- [x] `TaskRouter.route()` returns a route object containing `provider`, `model_client`, `model_id`, and `max_tokens`.
- [x] `build_provider_clients()` registers only providers with available API keys.
- [x] `BaseAgent` telemetry writes the routed provider instead of hardcoded Anthropic.
- [x] UI agent construction passes the route provider into agents.
- [x] Session and Knowledge Library summaries can route through the economy tier for OpenAI parity evals.
- [x] Full suite passed: `uv run pytest tests/ -q --tb=no` — 389 passed, 5 warnings.

**Not in scope for this fix:**

- Automatic provider failover.
- Model quality auto-promotion based on telemetry.
- UI controls for provider selection.
- Pricing/cost dashboard.
- Gemini support.

---

---

### Phase 6 — Constructor Fallback Chain + System Warnings

**Goal:** Remove Phase 1's silent import-time env var defaults; make the fallback chain explicit and observable; persist operational anomalies to a queryable table for periodic tech debt review.

**Prerequisites:** Phase 4 manual evals (T1–T7) signed off.

**Design decisions recorded:**
- Module-level `_MODEL = os.environ.get(...)` in agent files was a Phase 1 artifact that survived Phase 4. It resolves at import time before routing is attempted, making it a silent default rather than an intentional fallback. Tests built against it test an accidental path.
- The correct shape: resolution happens at construction time with an ordered fallback chain so the nominal path (TOML routing) always runs first.
- Env vars are kept but demoted to step 3 of the chain — intentionally a fallback, clearly labeled as such in `.env.example`.
- Silent fallbacks are undetectable; a `system_warnings` table gives the project a queryable record of operational anomalies. CLI surface first; UI panel deferred to UI-3.
- Iteration limits (`_MAX_TURNS = 10`, per-agent `max_tool_iterations` defaults, `NEURODB_RESEARCH_MAX_TOOL_ITERATIONS`) are MVP-era tuning values hardcoded in source or hidden in env vars. They belong in a `[tuning]` section in `neurodb_models.toml` alongside `max_tokens` for the same reason: they are per-task behavioral limits, not structural code.
- `_RELEVANCE_THRESHOLD = 0.7` in `session_manager.py` is a production tuning parameter (cosine distance cutoff for prior context injection) with no config path. It belongs in `[tuning]` for the same reason as iteration limits.
- Model API errors (rate limits, auth failures, network timeouts, malformed responses) currently propagate silently to the Streamlit UI with no persistent record. `chat()` and `chat_stream()` re-raise exceptions after rolling back message history, so the error is visible in the UI but not logged or stored. API errors belong in `system_warnings` with `warning_type = "model_api_error"` — same infrastructure as the fallback chain warnings, no additional table needed. `logging.error()` fires for real-time visibility; the DB write is the durable record.

**Fallback chain (in `BaseAgent._resolve_model()`):**
1. Explicit `model=` passed by caller → use it (nominal path, caller did routing via TaskRouter)
2. `get_model_for_task(task_type)` from TOML → use it (nominal path, self-resolving)
3. `os.environ.get(FALLBACK_ENV_VAR)` → use it; emit `logging.warning()` + write `SystemWarning` row
4. Hardcoded last-resort default → use it; emit `logging.warning()` + write `SystemWarning` row

#### Task 6.0 — Manual test plan

- [ ] Create `docs/testsPlans/manualTestPlan_config_phase6.md` covering: nominal TOML path, fallback fires and logs warning, warning row written to DB, CLI query returns it
- [ ] Add plan to `docs/projectStatus.md` reference table

#### Task 6.1 — TOML `[tuning]` section and config helper

- [ ] Add `[tuning]` section to `neurodb_models.toml` with:
  - `max_tool_iterations_standard = 10` — default for db and tutor agents
  - `max_tool_iterations_research = 25` — research agent loop
  - `session_relevance_threshold = 0.7` — cosine distance cutoff for prior context injection in `session_manager.py`
- [ ] Add `get_tuning_value(key, default=None)` to `src/neurodb/config/model_config.py`; reads from the TOML `[tuning]` section; returns `default` if key is absent (allows safe reads without breaking on older TOML files)
- [ ] Write failing tests: `get_tuning_value("max_tool_iterations_standard")` returns 10; missing key with default does not raise; missing key without default raises `KeyError`
- [ ] Run tests — confirm red; implement; confirm green
- [ ] Run full `uv run pytest tests/ -q --tb=no`

#### Task 6.1b — Wire iteration limits and relevance threshold from TOML

- [ ] In `db_agent.py` and `tutor_agent.py`: replace hardcoded `max_tool_iterations=10` default with `get_tuning_value("max_tool_iterations_standard", 10)`
- [ ] In `research_agent.py`: replace `NEURODB_RESEARCH_MAX_TOOL_ITERATIONS` env var read with `get_tuning_value("max_tool_iterations_research", 25)`; remove env var read
- [ ] In `session_manager.py`: replace `_RELEVANCE_THRESHOLD = 0.7` with `get_tuning_value("session_relevance_threshold", 0.7)`
- [ ] Comment out `NEURODB_RESEARCH_MAX_TOOL_ITERATIONS` in `.env.example`; add note that it is now owned by `neurodb_models.toml [tuning]`
- [ ] Write failing tests: agents pick up iteration limit from TOML; `session_manager` picks up threshold from TOML; both fall back to coded default if key absent
- [ ] Run tests — confirm red; implement; confirm green
- [ ] Run full `uv run pytest tests/ -q --tb=no`

#### Task 6.2 — `SystemWarning` schema

- [ ] Add `SystemWarning` ORM table to `src/neurodb/schema.py` with columns: `id`, `logged_at`, `warning_type`, `task_type`, `reason`, `fallback_step`, `resolved_value`
- [ ] Add migration to create `system_warnings` for existing DB files
- [ ] Write failing schema test: table created by `init_db`
- [ ] Run test — confirm red; implement; confirm green
- [ ] Run full `uv run pytest tests/ -q --tb=no`

#### Task 6.3 — Warning telemetry helper

- [ ] Add `record_system_warning(engine, warning_type, task_type, reason, fallback_step, resolved_value)` to `src/neurodb/model_telemetry.py`; write failure must be swallowed (same pattern as `record_model_call`)
- [ ] Write failing tests: row written with correct fields; write failure does not propagate
- [ ] Run tests — confirm red; implement; confirm green
- [ ] Run full `uv run pytest tests/ -q --tb=no`

#### Task 6.4 — Constructor fallback chain

- [ ] Add `_resolve_model(task_type, fallback_env_var, hardcoded_default, engine)` to `BaseAgent`
- [ ] Steps 3 and 4 call `logging.warning()` with task type, reason, fallback step, and resolved value
- [ ] Steps 3 and 4 call `record_system_warning()` non-blockingly
- [ ] `model=` parameter on `BaseAgent.__init__` defaults to `None`; constructor calls `_resolve_model()` when `None`
- [ ] Write failing tests: explicit `model=` bypasses resolution; TOML path resolves correctly; step-3 warning fires when TOML raises; step-4 warning fires when env var is also unset
- [ ] Run tests — confirm red; implement; confirm green
- [ ] Run full `uv run pytest tests/ -q --tb=no`

#### Task 6.5 — Remove module-level env var reads

- [ ] Remove `_MODEL = os.environ.get(...)` from `db_agent.py`, `tutor_agent.py`, `research_agent.py`
- [ ] Remove `_SUMMARY_MODEL = os.environ.get(...)` from `session_manager.py`
- [ ] Remove `NEURODB_PREMIUM_MODEL = os.environ.get(...)` from `hypothesis_review.py`
- [ ] Remove legacy env var read from `knowledge_library.py`; rely on constructor resolution
- [ ] Each agent passes its `task_type` (e.g. `"agent.loop.local_db"`) and `fallback_env_var` (e.g. `"NEURODB_AGENT_MODEL"`) to `BaseAgent.__init__`
- [ ] Update all affected tests: replace env var patches with either explicit `model=` or TOML-path assertions
- [ ] Run full `uv run pytest tests/ -q --tb=no`

#### Task 6.6 — `.env.example` transition note

- [ ] Comment out all five legacy model vars in `.env.example`
- [ ] Add block comment explaining these fire only when TOML routing is unavailable (e.g. missing file, unknown task type) and that normal operation uses `neurodb_models.toml` via TaskRouter

#### Task 6.7 — CLI warnings surface

- [ ] Create `src/neurodb/cli/warnings.py`
- [ ] Implement: query `system_warnings` ordered by `logged_at DESC`; accept optional `--limit` (default 20) and `--since` (ISO date) flags; print tabular output to stdout
- [ ] Write failing test: CLI returns rows present in DB; empty table prints a clear "no warnings" message
- [ ] Run tests — confirm red; implement; confirm green
- [ ] Run full `uv run pytest tests/ -q --tb=no`
- [ ] Update `docs/projectStatus.md` with final test count

#### Task 6.8 — Model API error logging

- [ ] In `BaseAgent.chat()`: wrap `yield from self._chat_inner(...)` so that on exception, before re-raising, emit `logging.error()` with provider, model, task type, and exception message; call `record_system_warning()` with `warning_type="model_api_error"`
- [ ] In `BaseAgent.chat_stream()`: same pattern
- [ ] Warning fields: `task_type=self._telemetry_task_type`, `reason=str(exc)`, `fallback_step="api_call"`, `resolved_value=f"{self._model_provider}/{self._model}"`
- [ ] Write failing tests: API exception triggers `logging.error()` and writes `system_warnings` row; exception still propagates to caller
- [ ] Run tests — confirm red; implement; confirm green
- [ ] Run full `uv run pytest tests/ -q --tb=no`

#### Task 6.9 — Phase 6 evals (manual)

| Eval | Pass criteria |
|------|---------------|
| Nominal TOML path | Agent constructs normally; no warning logged; no `system_warnings` row written |
| TOML unavailable (task type removed) | `logging.warning()` fires at step 3 or 4; `system_warnings` row written with correct fields |
| CLI query | `uv run python -m neurodb.cli.warnings` returns the warning row from the previous eval |
| Iteration limit from TOML | Change `max_tool_iterations_standard` in TOML; confirm agent loop respects updated value without code change |
| Relevance threshold from TOML | Change `session_relevance_threshold` in TOML; confirm prior-context injection behavior shifts accordingly |
| Model API error captured | Trigger an API error (e.g. invalid model ID); confirm `logging.error()` fires, `system_warnings` row written, exception still surfaces in UI |
| All existing Phase 4 evals re-run | No regression in agent behavior |

- [ ] All Phase 6 evals pass before closing the phase

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
