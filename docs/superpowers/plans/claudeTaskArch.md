# Model Routing Architecture — Design Plan

**Date:** 2026-05-07
**Status:** Design only — no implementation
**Analysis sources:** `docs/claudeTaskAnalysis.md`, `docs/codexTaskAnalysis.md`

---

## Executive Summary

NeuroDb currently routes all model calls through a single global env var that defaults to `claude-opus-4-7`. This made sense before the research agent existed; it is no longer appropriate. The research agent's 40-iteration loop pays Opus rates for orchestration work that a standard-tier model handles equally well. Most sessions now contain a mix of low-, mid-, and high-complexity tasks billed identically at the highest rate.

The fix is task-based model routing: each API call is assigned to the cheapest model that reliably meets the quality floor for that specific task type. This plan implements that routing in four phases, keeping Anthropic as the sole provider through Phase 3 while designing the architecture for multi-provider extensibility in Phase 4.

**Phase 1** replaces the single `NEURODB_MODEL` env var with per-purpose vars (agent loop → Sonnet, summaries → Haiku). This is the fastest cost reduction with the lowest risk.

**Phase 2** adds telemetry to measure actual token and iteration distribution before making stronger routing claims.

**Phase 3** splits the research agent into a Sonnet-backed retrieval/orchestration loop and a bounded Opus-backed hypothesis review step — the only place where premium spend is genuinely justified.

**Phase 4** adds a provider-neutral `ModelClient` interface, a config-driven model table, and a `TaskRouter`, enabling OpenAI and Groq without rewriting agent logic.

---

## Comparative Strengths and Weaknesses

This plan was developed alongside `docs/codexTaskAnalysis.md`, which contains a Codex-authored routing analysis. Both cover the same problem from different angles. Key differences:

| Dimension | This plan | codexTaskAnalysis.md |
|-----------|-----------|----------------------|
| **Structure** | Phased plan with scoped deliverables, success criteria, and out-of-scope table | Analysis document — no phased scope or success criteria |
| **Routing dimensions** | Six (task-type, model fit, turns, tokens, cost, quality) | Eight — adds `risk` and `context_size` as explicit drivers |
| **Escalation model** | Default tier per task only | Per-task escalation triggers (e.g. economy → standard on broad search queries) |
| **Telemetry** | Logging spec: fields and table schema | Feedback loop: telemetry actively feeds back into routing decisions over time |
| **Synthesis boundary** | Fully designed: boundary problem, three design options, recommended approach with rationale | Named and one-paragraph — design is underspecified |
| **ModelClient interface** | Full contract with normalized response and ContentBlock types | Illustrative pseudocode only |
| **Config table** | Complete: eval_status, last_verified_at, fallback fields, promotion/demotion process | Important fields (temperature, tool_support, streaming_support) listed in a trailing "later" section |
| **Provider notes** | Separate OpenAI and Groq entries | Groq shares OpenAI-compatible API — one adapter covers both |
| **Economy tier nuance** | Single economy tier for all search query formulation | Haiku for narrow topics, Sonnet for broad — more precise |
| **Eval gate** | Evals tied to phases with pass criteria | Evals listed but not connected to a promotion/demotion workflow |

**Gaps in this plan addressed by codexTaskAnalysis.md that should be incorporated:**

- `risk` and `context_size` as routing dimensions belong in the decision model (added to §Routing Dimensions below)
- Escalation triggers per task type — promoted to the task assignment table
- Telemetry as a feedback loop, not just logging — added to §Telemetry
- Economy vs. standard split for search query formulation — added to §Capability Tiers
- Groq as OpenAI-compatible — noted in §Phase 4 scope

---

## Problem

All NeuroDb agents default to `claude-opus-4-7` via the global `NEURODB_MODEL` env var. The research agent runs up to 40 tool iterations per user request. Most of those iterations perform orchestration tasks (SQL generation, search query formulation, tool-result interpretation) that a standard-tier model handles equally well. The result is that premium model rates are applied to low-complexity work at scale.

The core misalignment: **model assignment tracks agent identity, not task complexity.**

The fix is not simply reducing turns or tokens — that degrades capability. The fix is routing each call to the cheapest model that reliably meets the quality bar for that specific task type.

---

## Design Principles

1. **Task type drives model selection.** The kind of cognitive work being done — not which agent is running — determines the required capability tier.
2. **Quality is a constraint, cost is the objective.** For each task type, define a quality floor. Select the minimum-cost model that clears it.
3. **Tiers are stable; model IDs are not.** Capability tiers (premium / standard / economy) are fixed design concepts. Specific model IDs (claude-opus-4-7, claude-sonnet-4-6) change with provider releases and must live in config, not in source.
4. **Anthropic is the MVP provider.** The architecture is designed for provider-agnosticism, but all Phase 1–3 implementation uses Anthropic only.
5. **No silent model promotion.** New model generations are introduced as `candidate`, not `baseline`. They require passing task evals before becoming defaults.

---

## Routing Dimensions

Every model call is characterized by eight dimensions. The first four are inputs to the selection decision; the last four are outputs or feedback signals.

| Dimension | Role | Notes |
|-----------|------|-------|
| `task_type` | Selection input | The kind of cognitive work: SQL gen, tool orchestration, synthesis, summary, etc. Primary routing key. |
| `risk` | Selection input | Consequence of a weak answer. High-risk scientific claims justify a stronger tier or explicit review. |
| `context_size` | Selection input | Amount of history, tool schemas, and prior context resent per call. Large context makes even cheap models expensive; compaction matters. |
| `expected_iterations` | Selection input | Estimated turns for this task. High-iteration orchestration work must not default to premium. |
| `model` | Selection output | Concrete provider/model assigned after tier resolution. |
| `cost` | Optimization target | Turns × avg_tokens × price_per_token(model). Minimize subject to quality constraint. |
| `quality_outcome` | Feedback signal | Whether the call met the task-type quality floor. Feeds back into tier assignment over time. |
| `stop_reason` | Feedback signal | `end_turn`, `tool_use`, `max_tokens`, `budget_exhausted`. Flags misconfigurations (e.g. token truncation on synthesis). |

**Decision function:**

```
task_type + risk + context_size + expected_iterations
    → capability_tier
    → provider/model
    → max_tokens / budget
    → eval + telemetry feedback → adjust tier assignment
```

---

## Capability Tiers

| Tier | Role | Examples of qualifying tasks |
|------|------|------------------------------|
| `premium` | Deep scientific reasoning, epistemic calibration, synthesis under conflicting evidence | Hypothesis critique, final synthesis review, difficult confound identification |
| `standard` | Multi-step orchestration, domain-grounded judgment, structured generation | SQL generation, tool-result interpretation, relevance judgment, tutor explanation, hypothesis drafting, broad search query formulation |
| `economy` | Extraction, format adherence, template-fill from provided input | Session summary, Knowledge Library summary, research question field extraction, narrow search query formulation |

**Economy/standard split for search query formulation:** narrow or single-concept queries (e.g. "LTP mouse hippocampus") are economy-tier — the search API does the retrieval work. Broad, multi-concept, or ambiguous queries (e.g. "synaptic plasticity mechanisms relevant to learning across datasets") require standard-tier term selection and query shaping.

---

## Target Architecture

```
User request
    │
    ▼
Agent session
    │
    ├── Per-turn task classification
    │       │
    │       ▼
    │   TaskRouter
    │       │  task_type → capability_tier → provider/model
    │       ▼
    │   ModelClient (provider-neutral interface)
    │       │
    │       ├── AnthropicModelClient
    │       ├── OpenAIModelClient        (future)
    │       └── GeminiModelClient        (future)
    │
    ├── Tool dispatch (unchanged)
    │
    └── Telemetry
            task_type, model, provider, turns, tokens, stop_reason, cost, quality_outcome
```

**Phase 1–2:** No TaskRouter, no ModelClient abstraction. Per-agent env vars route at construction time (static assignment). Telemetry is added.

**Phase 3:** Research agent adds a bounded premium synthesis step. The loop runs on standard; a single Opus call handles synthesis over a compact evidence bundle. This is the first dynamic routing.

**Phase 4:** TaskRouter + ModelClient abstraction + config-driven model table + provider support beyond Anthropic.

---

## Components

### 1. Capability Tier Env Vars (Phase 1)

Replace the single `NEURODB_MODEL` with per-purpose variables. Each maps to a tier; tier maps to a concrete model.

| Env var | Tier | Used by |
|---------|------|---------|
| `NEURODB_AGENT_MODEL` | standard | Local DB, External DB, Neuro-Tutor agents |
| `NEURODB_RESEARCH_MODEL` | standard | Research agent loop iterations |
| `NEURODB_SUMMARY_MODEL` | economy | Session summary (`session_manager.py`) |
| `NEURODB_KNOWLEDGE_SUMMARY_MODEL` | economy | Knowledge Library source summary (`knowledge_library.py`) |
| `NEURODB_PREMIUM_MODEL` | premium | Hypothesis synthesis/review (Phase 3) |

Default values when env vars are unset:

| Env var | Default |
|---------|---------|
| `NEURODB_AGENT_MODEL` | `claude-sonnet-4-6` |
| `NEURODB_RESEARCH_MODEL` | `claude-sonnet-4-6` |
| `NEURODB_SUMMARY_MODEL` | `claude-haiku-4-5-20251001` |
| `NEURODB_KNOWLEDGE_SUMMARY_MODEL` | `claude-haiku-4-5-20251001` |
| `NEURODB_PREMIUM_MODEL` | `claude-opus-4-7` |

Each agent reads its own var at construction. `BaseAgent` itself does not change — the model is passed in from the call site, same as today.

---

### 2. Telemetry (Phase 2)

Lightweight structured logging on every model call. No external service required in Phase 2 — append to a local log or DuckDB table.

Fields logged per call:

| Field | Description |
|-------|-------------|
| `task_type` | Classified task (e.g. `agent.loop.research`, `summary.session`) |
| `provider` | Model provider (e.g. `anthropic`) |
| `model` | Exact model ID used |
| `mode` | Agent mode (local_db, neuro_tutor, neuro_research, etc.) |
| `tool_name` | Tool dispatched in this iteration, if any |
| `iteration` | Loop iteration number within the turn |
| `input_tokens` | Reported input token count |
| `output_tokens` | Reported output token count |
| `stop_reason` | `end_turn`, `tool_use`, `max_tokens`, `budget_exhausted` |
| `elapsed_ms` | Wall time for the call |
| `estimated_cost_usd` | Approximated from token counts and model pricing |

Telemetry serves two purposes: it answers the key empirical question ("How many iterations are actually standard-tier vs. premium-tier work?") and it feeds back into routing decisions over time.

**Feedback loop:**

```
Current tier assignment
    → run model calls
    → log task_type, model, tokens, stop_reason, quality_outcome
    → query: which task types frequently hit max_tokens? (under-budgeted)
    → query: which task types have stop_reason=end_turn at low token counts? (over-tiered)
    → query: which tasks fail quality evals at current tier? (under-tiered)
    → adjust tier assignment or max_tokens for that task type
    → re-run evals to confirm improvement
```

Without this loop, tier assignments remain fixed assumptions. With it, they become empirically validated routing decisions that improve as the app accumulates usage data.

---

### 3. Research Synthesis Split (Phase 3)

**The synthesis boundary problem:**

`draft_hypothesis` is a persistence tool, not a synthesis tool. By the time the loop model calls `draft_hypothesis`, it has already generated `title`, `mechanism`, `evidence`, `predictions`, `datasets`, `confounds`, and `limitations` in the tool input. Switching model inside `_execute_tool_block` would be too late — synthesis has already happened.

**Recommended design: two-step draft/review**

This is the safest Phase 3 implementation because it keeps the premium call explicit, bounded, and user-triggered.

```
Step 1 — Standard loop drafts hypothesis
    Research loop (Sonnet) gathers evidence and calls draft_hypothesis.
    Hypothesis is persisted with status = "draft".

Step 2 — Premium review (explicit, user-triggered)
    User requests "Review hypothesis" in the Research workspace.
    A single bounded Opus call receives the compact hypothesis + evidence bundle.
    Opus returns a structured critique: unsupported claims, missing confounds,
    weak evidence links, suggested revisions.
    Result is stored as a review artifact linked to the hypothesis row.
    User can accept revisions and re-save, or keep the original draft.
```

Alternative designs (lower priority):

- **New synthesis tool:** Standard loop retrieves evidence, then calls a dedicated `synthesize_hypothesis` tool that makes the premium call internally and returns structured fields for persistence. Cleaner architecturally but more invasive to the existing tool schema.
- **Pre-persistence review:** Standard model proposes all fields; premium model critiques before `draft_hypothesis` is called. Requires a two-model turn within a single iteration, which complicates the loop.

**The two-step design is preferred because:**
- No changes to the existing tool schema or loop logic
- The premium call is bounded (compact evidence bundle, not full conversation history)
- The user controls when to spend the premium call
- Fits the existing Research workspace UI pattern (explicit actions panel)

---

### 4. ModelClient Abstraction (Phase 4)

A provider-neutral interface that `BaseAgent` calls instead of the Anthropic SDK directly.

**Interface contract:**

```python
class ModelClient(ABC):
    def create_message(
        self,
        model: str,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int,
    ) -> ModelResponse: ...

    def stream_message(
        self,
        model: str,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int,
    ) -> ModelStream: ...

    def format_tool(self, tool_definition: dict) -> dict: ...
    def format_tool_result(self, tool_use_id: str, content: str) -> dict: ...
```

**Normalized response contract:**

```python
@dataclass
class ModelResponse:
    stop_reason: str          # "end_turn" | "tool_use" | "max_tokens"
    content: list[ContentBlock]

@dataclass
class ContentBlock:
    type: str                 # "text" | "tool_use"
    text: str | None
    tool_name: str | None
    tool_use_id: str | None
    tool_input: dict | None
```

Provider implementations handle the translation between the provider's SDK format and this normalized contract. `BaseAgent._chat_inner` and `_chat_stream_inner` call `ModelClient` methods only — never `self._client.messages.create()` directly.

**Why this matters for tool schemas:** Anthropic uses `input_schema`; OpenAI uses `parameters`. The `format_tool()` method handles the translation so tool definitions in `TOOLS` dicts stay provider-neutral.

---

### 5. Config-Driven Model Table (Phase 4)

Model IDs live in `neurodb_models.toml`, not in source or env vars. The config maps tier → provider → current model ID with metadata.

**Config structure:**

```toml
[tiers.economy]
description = "Structured extraction, summaries, template-fill tasks"
default_provider = "anthropic"

[tiers.economy.providers.anthropic]
model = "claude-haiku-4-5-20251001"
eval_status = "baseline"
last_verified_at = "2026-05-07"

[tiers.standard]
description = "RAG loop orchestration, relevance judgment, tutor explanations"
default_provider = "anthropic"

[tiers.standard.providers.anthropic]
model = "claude-sonnet-4-6"
eval_status = "baseline"
last_verified_at = "2026-05-07"

[tiers.premium]
description = "Scientific synthesis, final critique, difficult reasoning"
default_provider = "anthropic"

[tiers.premium.providers.anthropic]
model = "claude-opus-4-7"
eval_status = "baseline"
last_verified_at = "2026-05-07"

[tasks]

[tasks."summary.session"]
tier = "economy"
max_tokens = 512

[tasks."summary.knowledge_source"]
tier = "economy"
max_tokens = 700

[tasks."agent.loop.local_db"]
tier = "standard"
max_tokens = 2048

[tasks."agent.loop.tutor"]
tier = "standard"
max_tokens = 2048

[tasks."agent.loop.research"]
tier = "standard"
max_tokens = 2048

[tasks."research.hypothesis_review"]
tier = "premium"
max_tokens = 4096
```

**Key config fields per provider entry:**

| Field | Purpose |
|-------|---------|
| `model` | Current pinned model ID |
| `eval_status` | `baseline` (default), `candidate` (under eval), `deprecated` |
| `last_verified_at` | Date last confirmed working for this task type |
| `fallback_provider` | Provider to use if primary fails (optional) |
| `fallback_model` | Model to use on fallback (optional) |

**Model generation update process:**

1. New model released by provider
2. Add entry in config with `eval_status = "candidate"`
3. Run task evals against the candidate
4. On pass: change `eval_status` to `baseline`, update `model` field
5. Old model moves to `eval_status = "deprecated"` with a sunset date

---

### 6. TaskRouter (Phase 4)

Maps task type string → `ModelClient` instance backed by the config table.

```python
class TaskRouter:
    def route(self, task_type: str) -> tuple[ModelClient, str, int]:
        """Return (client, model_id, max_tokens) for the given task type."""
        ...
```

Phase 1–3 don't need `TaskRouter` — agents read their env var at construction. `TaskRouter` becomes relevant in Phase 4 when the research agent needs to route the synthesis step to a different client than the loop.

---

## Eval Requirements

No model tier change ships without passing task evals. These are the minimum evals before each phase goes to production.

### Phase 1 evals (standard → loops, economy → summaries)

| Eval | Model | Pass criteria |
|------|-------|---------------|
| Local DB query (SQL gen + result) | Sonnet | Correct SELECT, correct result, no fabricated IDs |
| External DB discovery | Sonnet | Valid source calls, grounded candidates |
| Neuro-Tutor explanation | Sonnet | Clear, accurate, Knowledge Library referenced where relevant |
| Session summary | Haiku | Correct date/topic/concepts, no invented datasets |
| Knowledge Library summary | Haiku | Useful structured summary, no invented DOI or source claims |

### Phase 3 evals (synthesis split)

| Eval | Model | Pass criteria |
|------|-------|---------------|
| Research loop draft hypothesis | Sonnet | Evidence, predictions, datasets, confounds, limitations present; draft status set |
| Premium review critique | Opus | Identifies at least one unsupported claim or missing confound in a deliberately weak draft |
| No double persistence | Both | Hypothesis row written exactly once per request |

---

## Phased Implementation

### Phase 1 — Per-agent env vars (Anthropic MVP)

**Goal:** Stop using Opus as the universal default.

**Scope:**
- Read `NEURODB_AGENT_MODEL` in `NeuroDbAgent` and `NeuroTutorAgent` constructors (currently both use `NEURODB_MODEL`)
- Read `NEURODB_RESEARCH_MODEL` in `NeuroResearchAgent` constructor
- Read `NEURODB_SUMMARY_MODEL` in `session_manager.py` `_generate_summary()`
- Read `NEURODB_KNOWLEDGE_SUMMARY_MODEL` in `knowledge_library.py` `_generate_summary()`
- Set defaults to Sonnet (agents), Haiku (summaries)
- Update `.env.example`
- Pass Phase 1 evals before merging

**Not in scope:** Telemetry, synthesis split, provider abstraction, config table.

---

### Phase 2 — Cost telemetry

**Goal:** Measure actual cost and iteration distribution before claiming savings.

**Scope:**
- Add a `model_call_log` table (DuckDB) or append-only log file
- Instrument `_chat_inner` and `_chat_stream_inner` in `BaseAgent` to write one row per call
- Instrument `_generate_summary` in `session_manager.py` and `knowledge_library.py`
- Log all fields from the telemetry field table above
- No UI surface required in Phase 2 — raw table or log file is sufficient

**Not in scope:** Querying or visualizing telemetry, synthesis split, provider abstraction.

---

### Phase 3 — Research synthesis split

**Goal:** Reserve a bounded Opus call for hypothesis review; loop runs on Sonnet.

**Scope:**
- Add `NEURODB_PREMIUM_MODEL` env var, default `claude-opus-4-7`
- Add "Review Hypothesis" action to Research workspace UI
- Implement premium review call: receives compact hypothesis + evidence bundle, returns structured critique
- Store critique as a review artifact linked to the `draft_hypotheses` row (new `hypothesis_reviews` table or JSONB column)
- Pass Phase 3 evals before merging

**Not in scope:** Provider abstraction, config table, TaskRouter.

---

### Phase 4 — Provider abstraction + config-driven model table

**Goal:** Decouple model selection from Anthropic SDK specifics; make model generation updates a config change.

**Scope:**
- `ModelClient` abstract interface + `AnthropicModelClient` implementation
- Refactor `BaseAgent` to call `ModelClient` instead of `self._client.messages.*` directly
- `neurodb_models.toml` config file with tier/task/model/eval_status table
- `TaskRouter` that reads config and returns `(ModelClient, model_id, max_tokens)`
- `OpenAIModelClient` implementation (Groq shares OpenAI-compatible API — one adapter covers both)
- Eval gate before promoting any candidate model to baseline

**Not in scope:** Automated latest-model discovery, automated model promotion, Gemini provider (deferred — Gemini tool-use API differs more significantly from Anthropic/OpenAI).

---

## What Is Explicitly Out of Scope

| Feature | Why deferred |
|---------|-------------|
| Automated "latest model" discovery | Creates instability — provider releases don't guarantee quality for NeuroDb's task types |
| Automated model promotion | Requires eval gate; cannot be fully automated without a test harness |
| Gemini provider | Tool-use and streaming API differs significantly from Anthropic/OpenAI; deferred to after OpenAI adapter is stable |
| Dynamic per-turn routing inside the research loop | The two-step draft/review design covers the high-value case without needing in-loop model switching |
| Model cost dashboard UI | Phase 2 telemetry table is sufficient; dashboard is a later polish item |

---

## Success Criteria by Phase

| Phase | Success criteria |
|-------|-----------------|
| 1 | All Phase 1 evals pass; Opus no longer used for agent loops or summaries by default; `.env.example` updated; 319 tests still pass |
| 2 | Every model call writes a telemetry row; query on telemetry table returns model, tokens, stop_reason per call; no regressions |
| 3 | Hypothesis draft uses Sonnet; "Review Hypothesis" action triggers one bounded Opus call; critique stored and linked; Phase 3 evals pass |
| 4 | `BaseAgent` has no direct Anthropic SDK import; `AnthropicModelClient` passes all existing tests; `OpenAIModelClient` passes Phase 1 evals against OpenAI models; config table drives model selection |

---

## References

- `docs/claudeTaskAnalysis.md` — Task taxonomy, dimension framework, capability tier design, use case → task composition
- `docs/codexTaskAnalysis.md` — Routing decision model, telemetry fields, eval table, MVP vs. planned feature matrix, draft_hypothesis code constraint
- `src/neurodb/agents/base.py` — Current agent loop; Phase 1 and Phase 4 change here
- `src/neurodb/agents/research_agent.py` — Research agent; Phase 1 and Phase 3 change here
- `src/neurodb/agents/db_agent.py` — DB/External agent; Phase 1 changes here
- `src/neurodb/agents/tutor_agent.py` — Tutor agent; Phase 1 changes here
- `src/neurodb/session_manager.py` — Session summary; Phase 1 changes here
- `src/neurodb/ui/pages/knowledge_library.py` — Knowledge Library summary; Phase 1 changes here
- `src/neurodb/ui/pages/chat.py` — Agent construction; Phase 1 changes here
