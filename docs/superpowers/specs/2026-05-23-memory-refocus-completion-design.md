# Learning and Research Memory Refocus — Completion Phase

**Date:** 2026-05-23
**Epoch:** DB (LOG-059), Config Control (Sections 2–4), Agent Core / Tutor / Research (Section 5)
**Status:** Design approved — implementation plan pending
**Resolves:** LOG-059 (study log inner join drops anchors), LOG-054 (dataset usefulness invisible to agents)
**Completes:** Learning and Research Memory Refocus Phase 6 (`docs/superpowers/specs/2026-05-18-learning-research-memory-refocus-design.md`)

---

## Goals

1. Fix the study log correctness gap: topic/concept/paper-anchored notes are silently excluded from `list_tags()` and `search_tags()` due to an INNER JOIN on `DatasetIndex`.
2. Add per-mode context budgets to cap retrieval size as the corpus grows.
3. Surface retrieval counts in telemetry so operators can see whether local context is being used.
4. Complete the TOML task-type table with extraction, claim-review, synthesis, and grounded-review entries.
5. Surface dataset usefulness state in agent context so agents stop treating sparse records as research-ready evidence.

---

## Section 1 — LOG-059: Study Log Correctness

### Problem

`list_tags()` and `search_tags()` in `src/neurodb/study.py` both use SQLAlchemy `.join()` (INNER JOIN) on `DatasetIndex`. `StudyNote.index_id` became nullable in Phase 2 when topic/concept/paper anchors were added. Any note with `index_id = NULL` is silently dropped from all study log API responses.

### Fix

Change both joins to `.outerjoin()`. When `index_id` is NULL, resolve the display anchor from whichever non-null FK exists, joining `Topic`, `Concept`, and `Paper` as outer joins. Precedence when multiple FKs are set: `index_id` → `topic_id` → `concept_id` → `paper_id`.

| Anchor | `source` value | `source_id` value |
|--------|---------------|-------------------|
| `index_id` set | `datasets_index.source` | `datasets_index.source_id` |
| `topic_id` set | `"topic"` | resolved `topics.name` |
| `concept_id` set | `"concept"` | resolved `concepts.name` |
| `paper_id` set | `"paper"` | `papers.doi` or `papers.title[:50]` |
| none set | `"note"` | `""` |

The `source` filter in `list_tags()` matches against the resolved source string. Non-dataset notes (`source = "topic"`, `"concept"`, `"paper"`) pass through when filter is `"all"` and are excluded when a specific dataset source is selected — correct behavior since they are not dataset records.

### Frontend impact

No schema or API contract changes. The `StudyNote` API response already returns `source` and `source_id` as strings. The frontend source filter dropdown has hardcoded dataset-source options plus `"All sources"` — non-dataset notes appear only under `"All sources"`, which is the correct default.

### Files affected

- `src/neurodb/study.py` — `list_tags()`, `search_tags()`: outerjoin + anchor resolution
- `src/neurodb/schema.py` — no changes; `Topic`, `Concept`, `Paper` already exist

---

## Section 2 — Context Budgets

### Problem

`ContextOrchestrator.build_bundle()` retrieves context with no cap. As papers, notes, claims, and datasets accumulate, grounded-mode bundles grow unbounded, increasing cost and latency.

### Config

Add a `[context_budgets]` section to `neurodb_models.toml` with per-mode item limits per retrieval category:

```toml
[context_budgets.general]
papers = 2
notes = 3
claims = 3
datasets = 1

[context_budgets.contextual]
papers = 5
notes = 8
claims = 6
datasets = 3

[context_budgets.grounded]
papers = 10
notes = 15
claims = 12
datasets = 5
```

Budgets are expressed as **max items per category**, not tokens. This avoids a token-counting dependency while still achieving the cost and latency goal.

### Implementation

`ModelConfig` (in `src/neurodb/config/model_config.py`) reads `[context_budgets]` and exposes a typed `ContextBudget` dataclass. `ContextOrchestrator.build_bundle()` accepts an optional `budget: ContextBudget | None` and passes each category limit as `limit=` to its retrieval calls. When no budget is configured for a mode, retrieval is uncapped (existing behavior preserved).

### Files affected

- `neurodb_models.toml` — add `[context_budgets.*]` sections
- `src/neurodb/config/model_config.py` — read budgets, expose `ContextBudget` dataclass
- `src/neurodb/agents/context_orchestrator.py` — accept and apply budget in `build_bundle()`

---

## Section 3 — Retrieval Telemetry

### Problem

`ModelCallLog` records model call cost and latency but not what context was retrieved. Operators cannot tell whether local context is being used or whether it improves workflows.

### Schema change

Migration 015 adds five nullable integer columns to `model_call_log`:

| Column | Meaning |
|--------|---------|
| `context_papers_count` | Papers injected in this turn |
| `context_notes_count` | Study notes injected |
| `context_claims_count` | Claims injected |
| `context_datasets_count` | Dataset records injected |
| `context_gap_count` | Evidence gaps reported |

`ModelCallLog` ORM class gains the same five fields. Existing rows have NULL for all five — the CLI and ORM handle NULL cleanly with no backfill required.

### Population

The context orchestrator returns counts alongside the bundle. The agent loop passes counts to `log_model_call()`. Turns with no context bundle (general mode, summary tasks) leave all five fields NULL.

### CLI surface

`neurodb-telemetry` gains a **Context Usage** section displayed when any rows have non-NULL context counts:

```
Context Usage (last 20 agent turns)
────────────────────────────────────────────────────────────────────
13:45:22 23/05/26  neuro_tutor    contextual   5p / 8n / 4c / 2d
13:44:01 23/05/26  neuro_research grounded     9p / 12n / 8c / 3d  2 gaps
```

`p` = papers, `n` = notes, `c` = claims, `d` = datasets. Turns where all counts are NULL are omitted.

### Files affected

- `src/neurodb/schema.py` — five new nullable columns on `ModelCallLog`
- `src/neurodb/db.py` — migration 015
- `src/neurodb/agents/context_orchestrator.py` — return counts from `build_bundle()`
- `src/neurodb/model_telemetry.py` — accept and persist context counts in `log_model_call()`
- `src/neurodb/cli/telemetry.py` — Context Usage section in output

---

## Section 4 — Task-Type Defaults

### Problem

`neurodb_models.toml` has task types for agent loops and summaries but no entries for extraction, claim review, synthesis, or grounded answer review. Future agent sub-tasks have no named routing home.

### Additions

```toml
[tasks."agent.extract"]
tier = "economy"
max_tokens = 1024

[tasks."agent.claim_review"]
tier = "premium"
max_tokens = 2048

[tasks."agent.synthesis"]
tier = "premium"
max_tokens = 4096

[tasks."agent.grounded_review"]
tier = "premium"
max_tokens = 2048
```

Tier rationale: extraction is format-fill from provided input (economy); claim review, synthesis, and grounded answer review require deep scientific reasoning against conflicting or sparse evidence (premium). This matches the tier role definitions in `docs/ConfigControl_EpochPlan.md`.

No agent code changes in this phase. These entries give future sub-task routing a named home in the TOML.

### Files affected

- `neurodb_models.toml` — four new `[tasks.*]` entries

---

## Section 5 — LOG-054: Dataset Usefulness in Agents

### Problem

`DatasetResearchPacket.usefulness_state` exists in the schema but is stripped when the context orchestrator packages dataset context. Agents receive dataset titles and descriptions with no signal about research readiness, and may present `sparse` records as supporting evidence.

### Changes

**Context bundle** — when `ContextOrchestrator` packages dataset records, each entry in the `datasets` list gains a `usefulness_state` key. No schema changes; the orchestrator already queries `DatasetResearchPacket`.

**Agent prompts** — both `NeuroTutorAgent` and `NeuroResearchAgent` system prompts gain a short directive:

- Tutor: when a dataset is `sparse`, note the gap rather than presenting the record as a learning resource. Suggest the user request enrichment if the dataset is relevant.
- Research: treat only `research_context_ready` or `analysis_ready` datasets as supporting evidence. Label `sparse` and `partial` records as insufficient for claims and note them as evidence gaps.

**Evidence lens** — the `context_summary_event` stream payload gains a `dataset_usefulness` breakdown:

```json
"dataset_usefulness": {
  "sparse": 2,
  "partial": 1,
  "research_context_ready": 1,
  "analysis_ready": 0
}
```

This field is additive — existing frontend consumers ignore unknown keys. The field is omitted when no datasets were retrieved.

**Scope note:** LOG-054 is partially resolved here. The usefulness signal is now visible to agents and the evidence lens. Deeper dataset enrichment (richer source-native harvesting for sparse records) remains a future DB epoch item.

### Files affected

- `src/neurodb/agents/context_orchestrator.py` — include `usefulness_state` in dataset bundle entries
- `src/neurodb/agents/tutor_agent.py` — prompt addition for usefulness-aware dataset citation
- `src/neurodb/agents/research_agent.py` — prompt addition for usefulness-aware evidence grounding
- `src/neurodb/agents/base.py` — `context_summary_event` payload: add `dataset_usefulness` breakdown

---

## Testing

### Automated

- `list_tags()` with a topic-anchored note: assert note appears in results with `source = "topic"`
- `list_tags()` with `source = "openneuro"` filter: assert topic-anchored note is excluded
- `search_tags()` with keyword matching a topic-anchored note text: assert note appears
- `ModelConfig.context_budgets`: assert correct budget returned per mode; assert uncapped when section absent
- `ContextOrchestrator.build_bundle()` with budget: assert each category is capped at budget limit
- `log_model_call()`: assert context count fields persisted when supplied; NULL when not supplied
- Migration 015: assert five new columns present after `init_db()`; idempotent on re-run
- `context_summary_event`: assert `dataset_usefulness` breakdown present when datasets retrieved; absent when none

### Manual

Manual test plan (`docs/testsPlans/manualTestPlan_memory_refocus_completion.md`) covers:

- T1: study log shows topic/concept/paper-anchored notes under "All sources" filter
- T2: source filter still excludes non-dataset notes when a specific source is selected
- T3: `neurodb-telemetry` Context Usage section appears after an agent turn with context
- T4: grounded-mode agent cites `research_context_ready` dataset as evidence; labels `sparse` dataset as insufficient
- T5: context budget limits visible in telemetry counts (grounded turn does not exceed configured maximums)

---

## Open Issues Resolved / Partially Resolved

| Log ID | Resolution |
|--------|-----------|
| LOG-059 | `list_tags()` and `search_tags()` converted to outer join with anchor resolution; topic/concept/paper-anchored notes visible in study log API |
| LOG-054 | Partially resolved: `usefulness_state` surfaced in agent context bundle and evidence lens; deeper dataset enrichment deferred to DB epoch |
