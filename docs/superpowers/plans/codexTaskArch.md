# Task-Based Model Routing — Design Plan

**Date:** 2026-05-07
**Status:** Design only — no implementation
**Source analysis:** `docs/claudeTaskAnalysis.md`, `docs/codexTaskAnalysis.md`

## Executive Summary

The Claude analysis is strong as a concise architecture direction: it clearly identifies task complexity as the routing basis, separates Path A from Path B, and names the correct long-term components: provider abstraction, config-driven model table, and task router. Its main weakness is that it treats the architecture as more straightforward than it will be in code: provider differences, telemetry, eval gates, and the `draft_hypothesis` synthesis boundary need more design discipline before implementation.

The Codex analysis is stronger on implementation constraints and risk control: it clarifies that `draft_hypothesis` is currently persistence, not synthesis; it treats quality as a floor constraint and cost as the optimization target; and it recommends an Anthropic-only MVP before provider abstraction. Its main weakness is that it is more conservative and operationally heavier: telemetry, evals, and staged review add process and may delay cost reduction if not phased carefully.

This plan combines both: use Claude's clean task-routing architecture as the target, but apply Codex's staged risk controls for the MVP. The recommended direction is:

1. Start with Anthropic-only per-purpose model routing.
2. Add call-level telemetry and task evals.
3. Add explicit premium hypothesis review over compact evidence bundles.
4. Move model IDs into config.
5. Add provider abstraction and OpenAI/Gemini only after the Anthropic routing path is stable.

## Architecture Comparison

| Analysis / architecture | Strengths | Weaknesses | Design implication |
|-------------------------|-----------|------------|--------------------|
| Claude analysis: task taxonomy | Clear and compact taxonomy; correctly identifies that agent sessions mix low, mid, and high-complexity work | Uses broad tier labels and concrete model names that may age quickly | Keep the taxonomy, but express implementation in stable tiers and config-driven model IDs |
| Claude analysis: Path A per-agent env vars | Fastest low-risk cost reduction; minimal architectural churn; Anthropic-only MVP is pragmatic | Per-agent routing is coarse; Research can still mix cheap orchestration and expensive synthesis in one model | Use Path A as the first cost-control milestone, not the final design |
| Claude analysis: Path B multi-provider routing | Correct long-term direction; names provider abstraction, config table, and task router | Understates provider adapter complexity and eval requirements; model examples may become stale | Preserve as target architecture, but gate behind telemetry and evals |
| Claude analysis: config-driven model table | Correctly separates capability tiers from model generation churn | The example table is too model-name-specific and lacks eval/fallback metadata | Extend config with `eval_status`, `last_verified_at`, fallback model, tool/streaming support, and task constraints |
| Claude analysis: recommended sequence | Good high-level ordering: env vars, telemetry, synthesis split, provider abstraction | Treats research synthesis split as MVP-ish without detailing current `draft_hypothesis` persistence boundary | Split synthesis only after defining review/persistence semantics |
| Codex analysis: routing decision model | Clarifies the actual decision function: task type, risk, context size, expected iterations, model fit, cost, quality | More complex than needed for first implementation | Use it to design telemetry and evals, not to block the first Anthropic routing change |
| Codex analysis: code constraint on `draft_hypothesis` | Prevents a flawed implementation where Opus is called after synthesis already happened | Forces a larger research-flow design before true per-task premium synthesis | Prefer two-step draft/review for the first premium-model feature |
| Codex analysis: Anthropic MVP first | Reduces risk and preserves current working tool-use behavior | Still Anthropic-specific and does not exploit OpenAI/Gemini pricing | Use as Phase 1 while designing provider abstraction in parallel |
| Codex analysis: telemetry and eval gates | Makes model routing empirical and protects quality | Adds schema, logging, and process overhead | Start with lightweight append-only telemetry; do not overbuild dashboards initially |
| Codex analysis: latest-generation policy | Correctly avoids silent model churn and protects reproducibility | Requires future maintenance workflow | Design config now, but defer latest-model candidate discovery |

## Combined Design Stance

| Decision area | Chosen stance |
|---------------|---------------|
| Near-term provider | Anthropic only |
| Near-term routing | Per-purpose model settings, not one global `NEURODB_MODEL` |
| Research loop default | Standard tier |
| Summary default | Economy tier or local template |
| Premium model use | Explicit synthesis/review only |
| `draft_hypothesis` handling | Do not treat current persistence tool as the premium synthesis boundary |
| Provider abstraction | Planned, not MVP |
| Model generation updates | Config-driven candidates, promoted only after evals |
| Quality control | Task evals and telemetry before broad default changes |
| Cost control | Reduce premium loop calls first; tune turns/tokens second |

## Purpose

Reduce NeuroDb agent API cost without weakening the integrated RAG/context workflow. The design routes model calls by task complexity, measured cost, and measured quality rather than by broad agent identity.

This is not an implementation plan for immediate code changes. It defines the target design, MVP boundary, later architecture, evaluation requirements, and decision tradeoffs.

## Core Thesis

NeuroDb should treat every model call as a routed work unit:

```text
task_type + risk + context_size + expected_iterations
    -> capability_tier
    -> provider/model
    -> max_tokens / budget
    -> eval + telemetry feedback
```

The current system mostly collapses this to one global `NEURODB_MODEL`. That is the cost problem. Research mode is expensive because many lower-complexity orchestration calls pay premium-model rates.

## Design Goals

1. Preserve NeuroDb's integrated RAG value: local DuckDB, Chroma retrieval, session memory, Knowledge Library, research artifacts, and tool-mediated persistence remain inside the app.
2. Stop using premium models as the universal default.
3. Match model tier to task complexity.
4. Keep Anthropic as the MVP provider to minimize immediate risk.
5. Design the architecture so OpenAI, Gemini, or other providers can be added later.
6. Decouple task tiers from rapidly changing model names through config.
7. Require telemetry and evals before promoting model/provider changes.

## Non-Goals

- Do not replace NeuroDb's RAG workflow with standalone ChatGPT Pro or Claude Pro usage.
- Do not implement provider abstraction in the MVP.
- Do not auto-switch to "latest" model generations without evals.
- Do not silently use premium models for every Research turn.
- Do not change scientific artifact quality standards to save cost.

## Current Problem

The app has four direct model-call sites:

| File | Function | Current behavior | Cost issue |
|------|----------|------------------|------------|
| `src/neurodb/agents/base.py` | `_chat_inner()` | Non-streaming loop uses agent model every iteration | Same model for all task types |
| `src/neurodb/agents/base.py` | `_chat_stream_inner()` | Streaming loop uses agent model every iteration | Multi-step loops multiply cost |
| `src/neurodb/session_manager.py` | `_generate_summary()` | Session summary uses global model | Summary task does not need premium model |
| `src/neurodb/ui/pages/knowledge_library.py` | `_generate_summary()` | Source summary uses global model | Template summary does not need premium model |

Research mode has the largest multiplier because it can involve many tool iterations and larger output budgets.

## Important Code Constraint

`draft_hypothesis` is currently a persistence tool, not a synthesis boundary.

Current flow:

1. Loop model receives evidence and tool schemas.
2. Loop model decides to call `draft_hypothesis`.
3. Loop model fills the hypothesis fields.
4. Tool persists the already-generated fields.

Therefore, routing only the `draft_hypothesis` handler to Opus would be too late. If premium synthesis is desired, the design needs a separate premium synthesis/review step before or after persistence.

## Task Taxonomy

| Task type | Capability need | Default tier | Premium trigger |
|-----------|-----------------|--------------|-----------------|
| SQL generation | Precision and schema adherence | Standard, deterministic where possible | Repeated invalid SQL |
| Search query formulation | Structured term selection | Economy or standard | Broad/ambiguous search strategy |
| Tool orchestration | State tracking and tool discipline | Standard | Repeated loop failure |
| Tool-result interpretation | Grounded JSON/result reading | Standard | Conflicting/sparse evidence |
| Relevance judgment | Domain vocabulary and local grounding | Standard | High-value or ambiguous relevance |
| Structured record writing | Extraction and field formatting | Economy or standard | Long/ambiguous context |
| Session summary | Template-fill summarization | Economy | Research-grade summary requirement |
| Knowledge source summary | Structured summary from metadata | Economy or local template | Canonical/high-value source |
| Pedagogical explanation | Clear and accurate teaching | Standard | Difficult conceptual synthesis |
| Draft hypothesis | Scientific coherence and required safeguards | Standard first | High-value artifact, weak/conflicting evidence |
| Final critique/review | Epistemic calibration and unsupported-claim detection | Premium | Explicit review |

## Capability Tiers

Use stable tier names in design; model names are config values.

| Tier | Role | MVP provider default |
|------|------|----------------------|
| `economy` | Summaries, extraction, template-fill tasks | Anthropic Haiku-class |
| `standard` | Tool loops, RAG orchestration, SQL/search, relevance judgment, tutor explanations | Anthropic Sonnet-class |
| `premium` | Scientific synthesis, final critique, difficult reasoning | Anthropic Opus-class |

## MVP Design: Anthropic-Only Routing

The MVP should reduce cost without introducing multi-provider complexity.

### MVP model settings

Use separate settings by purpose:

```text
NEURODB_AGENT_MODEL=<standard Anthropic model>
NEURODB_RESEARCH_MODEL=<standard Anthropic model>
NEURODB_SUMMARY_MODEL=<economy Anthropic model>
NEURODB_KNOWLEDGE_SUMMARY_MODEL=<economy Anthropic model>
NEURODB_PREMIUM_MODEL=<premium Anthropic model>
```

### MVP routing

| Workflow | Tier | Notes |
|----------|------|-------|
| Local DB chat | Standard | Common queries can later become deterministic |
| External DB discovery | Standard | Tool use and relevance judgment |
| Neuro-Tutor | Standard | Pedagogical explanation and source use |
| Neuro-Research loop | Standard | Tool orchestration, retrieval, cross-reference |
| Session summary | Economy | Fixed-format summary |
| Knowledge Library summary | Economy or local template | One-call source summary |
| Premium hypothesis review | Premium | Explicit user-triggered or high-risk flow |

### MVP pros

- Immediate cost reduction.
- Minimal architecture risk.
- Preserves existing Anthropic tool-use behavior.
- Avoids multi-provider schema differences during cost stabilization.
- Keeps NeuroDb's RAG loop intact.

### MVP cons

- Still Anthropic-specific.
- Still relies on manually updated model names.
- Does not yet exploit OpenAI/Gemini cost differences.
- Requires a later synthesis/review boundary to spend premium tokens precisely.

## Research Synthesis Design

Research should be split into stages:

```text
local retrieval -> standard-model orchestration/draft -> optional premium review
```

### Preferred design: two-step draft/review

1. Standard model retrieves evidence and drafts a hypothesis.
2. Draft persists with explicit status such as `draft` or `needs_review`.
3. User triggers premium review when the artifact is worth the cost.
4. Premium model critiques or revises the draft over a compact evidence bundle.
5. Reviewed artifact records provenance: draft model, review model, review timestamp, and limitations.

### Why this is preferred

- Keeps premium calls bounded and explicit.
- Avoids hidden cost during long loops.
- Fits current persistence model with less risk than pre-persistence model swapping.
- Supports later multi-provider premium review.

### Alternative: premium synthesis tool

A new tool could receive compact retrieved evidence and produce structured hypothesis fields through a premium call before persistence.

Pros:

- Premium model authors the hypothesis directly.
- Strong separation between retrieval and synthesis.

Cons:

- More complex tool semantics.
- Needs strict output validation.
- Higher risk of double persistence or invalid tool-history recovery if not carefully designed.

## Telemetry Design

Task routing should become empirical. Each model call should eventually log:

| Field | Purpose |
|-------|---------|
| `request_id` | Trace one user request across model calls |
| `session_id` | Link to chat/session context |
| `mode` | Local DB, External DB, Tutor, Research |
| `task_type` | Routing category |
| `provider` | Anthropic/OpenAI/Gemini/etc. |
| `model` | Concrete model ID |
| `tier` | Economy/standard/premium |
| `iteration` | Loop iteration number |
| `input_tokens` | Input cost driver |
| `output_tokens` | Output cost driver |
| `max_tokens` | Budget cap |
| `stop_reason` | End turn, tool use, max tokens, error |
| `tool_name` | Tool requested/executed, if any |
| `latency_ms` | User experience and provider comparison |
| `estimated_cost` | Cost attribution |
| `quality_outcome` | Eval/pass/fail/manual rating when available |

Telemetry should support answers to:

- Which task types consume the most cost?
- Which model handled each task?
- Did cheaper models pass?
- Where did quality degrade?
- Where did premium review materially improve output?

## Evaluation Plan

Before changing defaults or adding providers, define task-specific evals.

| Eval | Candidate tier | Pass criteria |
|------|----------------|---------------|
| Local DB query | Standard/deterministic | Correct result, no fabricated IDs |
| External discovery | Standard | Valid source calls, grounded candidates |
| Tutor explanation | Standard | Clear explanation, correct use of Knowledge Library |
| Session summary | Economy | Correct date/topic/concepts, no invented datasets |
| Knowledge summary | Economy | Useful summary, no invented DOI/source claims |
| Research question recording | Economy/standard | Concise persisted question and context |
| Dataset cross-reference | Standard | Local evidence used, limitations surfaced |
| Draft hypothesis | Standard | Evidence, predictions, datasets, confounds, limitations, draft-only status |
| Premium critique | Premium | Unsupported claims, missing confounds, and weak evidence identified |

Promote a model/provider to default only after it passes evals for the relevant task type.

## Future Architecture: Provider-Agnostic Path B

Path B should support multiple providers, but not as the MVP.

### Target flow

```text
task_type
  -> capability tier
  -> provider/model config
  -> provider adapter
  -> normalized response
  -> telemetry + eval feedback
```

### Provider adapter responsibilities

| Responsibility | Reason |
|----------------|--------|
| Normalize message format | Anthropic/OpenAI/Gemini differ |
| Normalize tool schema | Tool/function declarations differ |
| Normalize tool results | Tool-result message formats differ |
| Normalize streaming events | Streaming protocols differ |
| Surface token usage | Cost telemetry needs provider-specific usage fields |
| Surface stop reasons | Loop control needs normalized stop state |

### Candidate interface

```text
ModelClient
  create_message(request) -> ModelResponse
  stream_message(request) -> ModelStream
  normalize_tool_schema(tool) -> provider_tool
  normalize_tool_result(result) -> provider_message
```

Provider implementations:

- `AnthropicModelClient`
- `OpenAIModelClient`
- `GeminiModelClient`

## Config-Driven Model Table

Model names change quickly. The design should route by stable task/tier names and load provider/model IDs from config.

Example future config:

```toml
[tiers.economy]
description = "Structured extraction, summaries, template-fill tasks"
default_provider = "anthropic"

[tiers.economy.providers.anthropic]
model = "claude-haiku-current"
eval_status = "baseline"

[tiers.economy.providers.openai]
model = "gpt-mini-current"
eval_status = "candidate"

[tiers.standard]
description = "RAG loop orchestration, relevance judgment, tutor explanations"
default_provider = "anthropic"

[tiers.standard.providers.anthropic]
model = "claude-sonnet-current"
eval_status = "baseline"

[tiers.standard.providers.gemini]
model = "gemini-standard-current"
eval_status = "candidate"

[tiers.premium]
description = "Scientific synthesis, final critique, difficult reasoning"
default_provider = "anthropic"

[tiers.premium.providers.anthropic]
model = "claude-opus-current"
eval_status = "baseline"

[tasks.summary.session]
tier = "economy"
max_tokens = 512

[tasks.agent.loop.research]
tier = "standard"
max_tokens = 2048

[tasks.research.hypothesis_review]
tier = "premium"
max_tokens = 4096
```

Useful config fields:

- `provider`
- `model`
- `tier`
- `task_type`
- `max_tokens`
- `temperature`
- `tool_support`
- `streaming_support`
- `structured_output_support`
- `eval_status`
- `last_verified_at`
- `fallback_provider`
- `fallback_model`

## Latest-Generation Model Updates

Automatic latest-model selection should be planned for, not included in the MVP.

Design policy:

1. Use pinned model IDs for production-like workflows.
2. Track capability tiers in config.
3. Add a later utility that checks provider docs/APIs for newer models.
4. Mark newly discovered models as `candidate`.
5. Run task evals before promoting candidates to `baseline`.
6. Never silently promote a new model just because it is newer.

This gives NeuroDb an upgrade path without sacrificing reproducibility.

## Phased Roadmap

### Phase 1 — Anthropic model routing MVP

- Add per-purpose model settings.
- Route summaries to economy tier.
- Route interactive loops to standard tier.
- Keep premium model reserved for explicit review.
- No provider abstraction.

### Phase 2 — Cost telemetry

- Log call-level cost and routing fields.
- Attribute cost to task type and mode.
- Use telemetry to validate assumptions about expensive workflows.

### Phase 3 — Research premium review

- Add explicit premium review flow for hypotheses.
- Use compact evidence bundles.
- Track draft model and review model in artifact metadata.
- Keep premium calls bounded and user-visible.

### Phase 4 — Config table

- Move model IDs and tier mappings to config.
- Preserve env var overrides for local experimentation.
- Add eval status and last-verified metadata.

### Phase 5 — Provider abstraction

- Introduce provider-neutral model client.
- Keep Anthropic as baseline provider.
- Add OpenAI/Gemini as candidates behind eval gates.

### Phase 6 — Latest-generation candidate discovery

- Add utility to discover newer provider models.
- Update config candidates, not production defaults.
- Promote only after task evals pass.

## Design Risks

| Risk | Mitigation |
|------|------------|
| Cheaper model degrades research quality | Task evals and premium review |
| Provider abstraction delays cost savings | Anthropic-only MVP first |
| Dynamic model updates break reproducibility | Pin defaults and require eval promotion |
| Telemetry increases complexity | Start with append-only call log |
| Premium review becomes hidden cost | Make review explicit and bounded |
| Tool semantics differ across providers | Normalize through provider adapters only after MVP |

## Open Decisions

1. Should premium review be user-triggered only, or also automatically suggested when evidence is sparse/conflicting?
2. Should Knowledge Library summaries default to local templates or economy model calls?
3. Should common Local DB queries bypass LLMs through deterministic UI/query templates?
4. Where should model telemetry live: DuckDB table, local JSONL, or both?
5. Should config be TOML, JSON, or DuckDB-backed preferences?
6. What minimum eval set is required before changing the default model for each task type?

## Deliverables for a Future Implementation Plan

Before implementation, create:

- manual test plan for model-routing behavior,
- task eval fixture set,
- telemetry schema,
- model config schema,
- decision on MVP environment variable names,
- premium review UX plan,
- rollback plan for model default changes.

## Final Design Recommendation

Proceed in two tracks:

1. **Cost stabilization track:** Anthropic-only model routing, summaries on economy tier, loops on standard tier, premium review explicit.
2. **Architecture track:** Design provider-neutral `ModelClient`, task router, config-driven model table, and latest-generation candidate workflow, but implement only after telemetry and evals exist.

This keeps the near-term path pragmatic while preventing the architecture from becoming permanently Anthropic- and model-generation-specific.
