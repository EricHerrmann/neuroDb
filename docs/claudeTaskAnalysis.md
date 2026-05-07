# NeuroDb: Task-Level Model Routing and Multi-Provider Architecture Analysis

**Date:** 2026-05-07
**Status:** Design analysis — no implementation yet
**Companion docs:** `docs/codexTaskAnalysis.md`

---

## Context

LT-3 introduced the research agent with up to 40 tool iterations. API costs increased significantly. Root cause: all agents default to `claude-opus-4-7` via the global `NEURODB_MODEL` env var. The research agent's 40-iteration loop pays Opus rates for every call, including low-complexity tool dispatch.

The fix that shipped (LT-3 remediation) was `NEURODB_RESEARCH_MAX_TOKENS=4096`, which resolved the immediate `max_tokens` failure. Model routing is the next cost lever.

---

## Task Taxonomy

The fundamental insight: agent cost should track task complexity, not agent identity. The same agent session contains tasks at very different complexity levels.

| Task | What it does | Model strength needed |
|------|-------------|----------------------|
| SQL generation | Translate natural language → SELECT against fixed schema | Precision + format accuracy |
| Search query formulation | Translate topic → PubMed/Semantic Scholar query string | Structured reasoning |
| Tool-result interpretation + next step | Read JSON output, decide what to call next | Multi-step orchestration |
| Relevance judgment | Decide if dataset/source is relevant to topic | Domain vocabulary + judgment |
| Structured record writing | Populate fields for research questions, study notes | Instruction following |
| Scientific synthesis | Combine evidence into testable claim; identify confounds and limitations | Deep reasoning + epistemic calibration |
| Pedagogical explanation | Explain concepts clearly in teaching context | Clarity + accuracy |
| Template-fill summarization | Fill 5–6 fixed fields from existing text | Extraction + format adherence |

---

## Task → Model Assignment

| Task | Tier | Model |
|------|------|-------|
| SQL generation | Mid | Sonnet 4.6 |
| Search query formulation | Mid | Sonnet 4.6 |
| Tool-result interpretation + next step | Mid | Sonnet 4.6 |
| Relevance judgment | Mid | Sonnet 4.6 |
| Structured record writing | Low-Mid | Sonnet 4.6 |
| Scientific synthesis | High | Opus 4.7 |
| Pedagogical explanation | Mid | Sonnet 4.6 |
| Template-fill summarization | Low | Haiku 4.5 |

---

## Use Case → Task Composition

| Use case | Tasks | Dominant tier |
|----------|-------|---------------|
| Local DB | SQL gen, tool-result interp, structured record write | Mid → Sonnet |
| External DB | SQL gen, search query, relevance judgment, tool-result interp | Mid → Sonnet |
| Neuro-Tutor | Search query, tool-result interp, relevance judgment, pedagogical explanation | Mid → Sonnet |
| Research loop (iterations 1–N) | Search query, cross-ref lookup, tool-result interp, structured record write | Mid → Sonnet |
| Research loop (hypothesis step) | Scientific synthesis | High → Opus |
| Session summary | Template-fill summarization | Low → Haiku |
| Knowledge Library summary | Template-fill summarization | Low → Haiku |

---

## Key Correction: Where Synthesis Actually Happens

> See `docs/codexTaskAnalysis.md` §Current Code Constraint for the Codex analysis of this implementation boundary.

The `draft_hypothesis` tool is a **persistence tool, not a synthesis tool**. By the time the loop model calls `draft_hypothesis`, it has already generated `title`, `mechanism`, `evidence`, `predictions`, `datasets`, `confounds`, and `limitations` in the tool input. The tool only persists them.

This means a simple per-dispatch model swap at `_execute_tool_block` would be too late — the synthesis has already happened in the loop model's prior turn. To genuinely reserve Opus for synthesis, the architecture needs one of:

1. A new synthesis tool that receives compact evidence and returns structured hypothesis fields (Sonnet loop → Opus synthesis call → persistence)
2. A two-step draft/review: Sonnet drafts, user triggers an explicit Opus review pass
3. A pre-persistence review: Sonnet proposes draft, Opus critiques before persisting

---

## Implementation Paths

### Path A — Per-agent model env vars

Each agent reads its own env var. No architectural change.

```
NEURODB_AGENT_MODEL=claude-sonnet-4-6       # Local DB, External DB, Tutor
NEURODB_RESEARCH_MODEL=claude-sonnet-4-6    # Research loop
NEURODB_SUMMARY_MODEL=claude-haiku-4-5      # Session and Knowledge Library summaries
NEURODB_PREMIUM_MODEL=claude-opus-4-7       # Reserved for explicit synthesis step
```

Immediate cost reduction. Does not solve hypothesis synthesis quality unless a dedicated premium synthesis stage is added.

### Path B — Per-task model switching with multi-provider architecture

Proposed direction (not yet implemented):

- Sonnet handles the research loop orchestration
- A bounded Opus call handles hypothesis synthesis over a compact evidence bundle
- Architecture is provider-agnostic: Anthropic as MVP, OpenAI and Gemini extensible
- Model selection driven by a config table, not hardcoded model strings

See §Proposed Architecture below.

---

## Proposed Architecture: Multi-Provider + Config-Driven Model Routing

### Design Goals

1. Per-task model routing: tasks map to capability tiers, tiers map to current model IDs
2. Provider abstraction: client interface is provider-neutral; Anthropic, OpenAI, Gemini are implementations
3. Config-driven model table: current model IDs live in a config file, not hardcoded in source
4. Future-proof against generation churn: model names change; capability tiers do not

### Capability Tiers

| Tier | Role | Current Anthropic default |
|------|------|--------------------------|
| `premium` | Scientific synthesis, complex reasoning under conflicting evidence | claude-opus-4-7 |
| `standard` | Orchestration, SQL, search, relevance judgment, explanations | claude-sonnet-4-6 |
| `economy` | Template-fill summarization, structured extraction | claude-haiku-4-5-20251001 |

### Config Table (planned, non-MVP)

A config file (e.g. `neurodb_models.toml` or `neurodb_models.json`) maps tier → provider → current model ID:

```toml
[tiers.premium]
default_provider = "anthropic"

[tiers.premium.providers.anthropic]
model = "claude-opus-4-7"

[tiers.premium.providers.openai]
model = "gpt-4o"

[tiers.premium.providers.gemini]
model = "gemini-2.0-flash-thinking-exp"

[tiers.standard]
default_provider = "anthropic"

[tiers.standard.providers.anthropic]
model = "claude-sonnet-4-6"

[tiers.standard.providers.openai]
model = "gpt-4o-mini"

[tiers.economy]
default_provider = "anthropic"

[tiers.economy.providers.anthropic]
model = "claude-haiku-4-5-20251001"

[tiers.economy.providers.openai]
model = "gpt-4o-mini"
```

This decouples model generation updates from code changes. When Anthropic releases Sonnet 4.7, update the config, not the source.

### Provider Abstraction Layer (planned, non-MVP)

An abstract `ModelClient` interface wraps provider-specific SDKs:

```
ModelClient (abstract)
├── create_message(messages, tools, system, max_tokens) → response
├── stream_message(messages, tools, system, max_tokens) → stream
└── format_tool(tool_definition) → provider-specific format

AnthropicModelClient(ModelClient)
OpenAIModelClient(ModelClient)
GeminiModelClient(ModelClient)
```

The `BaseAgent` loop calls `ModelClient` methods. Swapping providers requires only swapping the `ModelClient` implementation.

### Task Router (planned, non-MVP)

A `TaskRouter` maps task type → tier → `ModelClient`:

```
TaskRouter
├── route(task_type: str) → ModelClient
└── (reads from config table + available API keys)
```

### MVP vs. Planned

| Feature | MVP | Planned |
|---------|-----|---------|
| Per-agent env vars (Path A) | Yes | — |
| Research synthesis split (Sonnet loop + Opus synthesis) | Yes | — |
| Provider abstraction layer | No | Phase 4 |
| Config-driven model table | No | Phase 4 |
| Task router | No | Phase 4 |
| OpenAI / Gemini providers | No | Phase 4 |

---

## Recommended Implementation Sequence

1. **Phase 1 (now):** Per-agent env vars — stop using Opus as universal default
2. **Phase 2:** Cost telemetry — log model, mode, tool, iteration, tokens, stop reason
3. **Phase 3:** Research synthesis split — Sonnet loop, explicit Opus synthesis stage over compact evidence
4. **Phase 4:** Provider abstraction + config-driven model table + multi-provider support

---

## Selection Framework: Turns, Tokens, Model, Task-Type, Fit, Cost, Quality

### Summary

Model selection for an agent turn is a multi-dimensional decision, not a single lookup. The six dimensions fall into three roles: **volume parameters** determine how much a decision costs at scale; **the selection criterion** determines what capability the turn actually needs; and **optimization targets** are what the selection is trying to balance.

The current system collapses all six dimensions into one: a single `NEURODB_MODEL` env var. Every turn in every agent pays the same model rate regardless of what it is doing. The research agent's 40-iteration loop makes this the dominant cost driver — not because any one call is expensive, but because Opus rates are applied to orchestration turns that Sonnet handles equally well.

The framework below separates the dimensions so each can be reasoned about independently.

### Dimension Table

| Dimension | Role | What it means | Example |
|-----------|------|---------------|---------|
| **Turns** | Volume parameter | How many times the agent calls the API in one user request; multiplies all per-call costs | Research agent: up to 40 turns per hypothesis request |
| **Tokens** | Volume parameter | Input context (grows with history, resent every turn) + output cap per call; determines per-call size | Research agent: 4096 output cap; input grows each iteration |
| **Task-type** | Selection criterion | The kind of cognitive work this specific turn requires; defines what capability is actually needed | Turn 7: tool-result interpretation (orchestration); Turn 35: scientific synthesis |
| **Model fit** | Selection criterion | Alignment between a model's capability and the task-type's requirement; overfitting wastes cost, underfitting loses quality | Opus for SQL generation = overfitting; Haiku for hypothesis synthesis = underfitting |
| **Cost** | Optimization target | Turns × avg tokens × price-per-token(model); the output you are minimizing | 35 Sonnet orchestration turns + 1 Opus synthesis turn << 36 Opus turns |
| **Quality** | Optimization target | How well the model output meets the task-type's requirement; treated as a per-task-type floor constraint | Orchestration quality floor: reliable tool dispatch; Synthesis quality floor: valid confounds and epistemic hedging |

### How the Dimensions Compose

```
task-type → minimum model fit → model assignment
model + turns + tokens        → cost
model + task-type             → quality
```

Quality is a **constraint** (must meet a floor per task-type). Cost is the **objective** to minimize within that constraint. Turns and tokens are **multipliers** that determine how consequential the model assignment is for a given task-type. Task-type and model fit are the **decision variables**.

### Why Turns and Tokens Are Not the Root Cause

Reducing turns (lower `max_tool_iterations`) or tokens (lower `max_tokens`) reduces cost mechanically but also reduces capability. The root misalignment is model fit: Opus is assigned to every turn regardless of task-type. Fixing the fit assignment captures most of the savings without sacrificing capability where it matters.

### Static vs. Dynamic Fit Assignment

Two ways to apply task-type routing:

| Mode | How it works | Tradeoff |
|------|-------------|----------|
| **Static** | Assign a model to an agent at construction time based on agent mode (Local DB → Sonnet; Research loop → Sonnet; synthesis step → Opus) | Simpler; covers most of the value; cannot distinguish orchestration turns from synthesis turns within one agent session |
| **Dynamic** | Classify each turn at dispatch time (e.g. by which tool is being called) and route to a different model per turn | More precise; captures the research loop split; requires the loop to hold multiple model clients and manage the synthesis boundary correctly |

Phase 1 (Path A) uses static assignment. Phase 3 (synthesis split) requires dynamic assignment for the research agent specifically.

---

## References

- `docs/codexTaskAnalysis.md` — Codex task-based cost analysis, code constraint analysis, provider-agnostic routing notes, and eval criteria
- `src/neurodb/agents/base.py` — Shared agent loop; model is fixed per agent session
- `src/neurodb/agents/research_agent.py` — Research agent; `_RESEARCH_MAX_TOKENS`, `_RESEARCH_MAX_TOOL_ITERATIONS`
- `src/neurodb/session_manager.py` — Session summary call; `_SUMMARY_MODEL`
- `src/neurodb/ui/pages/knowledge_library.py` — Knowledge Library summary call
