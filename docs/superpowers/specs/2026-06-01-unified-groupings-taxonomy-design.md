# Unified Groupings Taxonomy — Design Spec

**Date:** 2026-06-01
**Author:** Claude (brainstormed with user)
**Status:** Draft — awaiting user review
**Supersedes:** `docs/superpowers/specs/2026-06-01-topic-taxonomy-hierarchy-design.md` (hierarchy becomes a property of the unified model)
**Closes:** LOG-062 (semantic / agent-based grouping suggestion)
**Context:** `docs/researchQuestionDesignClaude.md` / `docs/researchQuestionDesignCodex.md` (neither addresses taxonomy generality or a common categorization mechanism)

---

## Problem

Categorization in NeuroDb is fragmented and brittle:

- `topics` and `concepts` are separate tables, each with their own join tables (`paper_topics`, `paper_concepts`, `topic_concepts`, `dataset_packet_topics`, `question_topics`, `question_concepts`) and `study_notes` anchor columns.
- The taxonomy is flat and granular — many specific terms (`circuit plasticity`, `interhemispheric plasticity`) with no general parent (`plasticity`) and no hierarchy.
- Question→topic/concept suggestion is literal case-insensitive substring matching against existing names; it cannot reason semantically and cannot introduce a category that does not yet exist. A general or off-domain question gets no suggestions.
- Adding any new kind of categorization (method, brain region, disease, question-type) today means new tables, new join tables, new routes, new UI — the project repeatedly hits this as capability uncovers new capability needs.

## Goals

- **One unified model** for every grouping type. "Topic" and "concept" become values of a `type` column, not separate tables. New grouping types cost **zero schema**.
- **Hierarchy** (parent/child) available to every type uniformly (e.g. `plasticity` owns `neuroplasticity`, `circuit plasticity`; `stroke` owns `stroke recovery`, …).
- **Semantic + agent-based matching**: an LLM ranks relevant existing groupings of a type for a question, and may **propose new groupings** that do not yet exist; the user confirms. This is the full fix for the gap and applies to topics and concepts (and future types) through one engine.
- **Hierarchy-aware behavior**: a child match also suggests its parent; filtering by a parent includes its descendants.
- **Phased, low-risk rollout**: the unified tables coexist with the legacy tables; consumers cut over one slice at a time; legacy stays as a safety net until the final drop. The user's gap is closed mid-way, not at the end.

## Non-Goals

- **Big-bang migration.** Explicitly phased (see Implementation Phases).
- **Arbitrary-depth hierarchy.** Single-level nesting only (a parent is top-level; no grandchildren).
- **Cross-type parents.** A grouping's parent must be the same `type`.
- **New anchor types beyond what exists.** Anchors generalize structurally (`anchor_type` column), but this spec only wires `question`, plus the existing paper/dataset/note/grouping relationships during backfill. Matching new anchor types semantically is future work.
- **Embedding-based matching.** The matcher is LLM/agent-based (per scoping); embeddings are not used for grouping suggestion.

---

## Data Model

Two tables replace `topics`, `concepts`, and their six join tables.

```
groupings
  id          INTEGER PRIMARY KEY
  type        VARCHAR(32)  NOT NULL      -- 'topic' | 'concept' | future types
  name        VARCHAR(256) NOT NULL
  parent_id   INTEGER                    -- self-reference; NULL = top-level; NO FK (see below)
  status      VARCHAR(16)  NOT NULL      -- 'active' | 'proposed' | 'archived'
  description TEXT
  created_at  VARCHAR(32)  NOT NULL
  updated_at  VARCHAR(32)  NOT NULL
  UNIQUE(type, name)                     -- name unique within a type
  INDEX(type), INDEX(parent_id), INDEX(status)

grouping_links
  id           INTEGER PRIMARY KEY
  grouping_id  INTEGER     NOT NULL
  anchor_type  VARCHAR(32) NOT NULL      -- 'question' | 'paper' | 'dataset_packet' | 'study_note' | 'grouping'
  anchor_id    INTEGER     NOT NULL
  status       VARCHAR(16) NOT NULL      -- 'pending' | 'confirmed'
  created_at   VARCHAR(32) NOT NULL
  UNIQUE(grouping_id, anchor_type, anchor_id)
  INDEX(anchor_type, anchor_id), INDEX(status)
```

**No foreign-key constraints**, by design. `parent_id` and the link columns are plain indexed integers; integrity is enforced in application code. Reason: DuckDB rejects `UPDATE` on any column of an FK-referenced row, and re-parenting / status changes require updates — the same limitation that forced migration 012 to rebuild tables without FK constraints (LOG-037). Honoring it from the start avoids painful rebuilds later.

**`topic_concepts` (grouping↔grouping)** is represented generically: a link with `anchor_type='grouping'` and `anchor_id` = the other grouping's id. This is why the link table generalizes cleanly even to grouping-to-grouping relationships.

### Type registry

Valid `type` values live in a small in-code registry (a dict/enum), not the DB. Each entry carries display metadata and per-type policy:

```
GROUPING_TYPES = {
  'topic':   GroupingTypeSpec(display='Topic',   allow_agent_proposal=True),
  'concept': GroupingTypeSpec(display='Concept', allow_agent_proposal=True),
  # future: 'method', 'brain_region', 'disease', 'question_type' — add a line, no schema change
}
```

Adding a grouping type = one registry line. No migration, no new table, no new route.

### Hierarchy invariant (single level)

A grouping may have at most one parent of the **same type**, and **a parent must itself be top-level**. Enforced in the store layer:

- Setting `parent_id=P` on `C` is rejected if `P.parent_id` is non-null (no grandchildren), if `P.type != C.type`, if `C` already has children, or if `P == C`.
- Violations surface as a typed error mapped to HTTP 422.

---

## Semantic + Agent Matching Engine

A single type-parameterized function replaces `extract_question_topics`:

`suggest_groupings(engine, *, anchor_type, anchor_id, anchor_text, gtype) -> dict`

1. Load active groupings of `gtype` (`id`, `name`, `description`, `parent_id`).
2. Call the model via `ModelClient`, routed by a new task type `agent.extract.groupings` in `neurodb_models.toml` (tier `standard`). The call passes `anchor_text` + the candidate list and forces a structured tool/JSON response (Groq-safe: every object schema declares `properties` + `required`, never a bare `{"type":"object"}` — per known Groq strict-schema behavior):
   ```json
   {
     "relevant_existing": [{"id": 12, "reason": "..."}],
     "proposed_new":      [{"name": "plasticity", "parent_name": null}]
   }
   ```
   `proposed_new` is only honored when the type's `allow_agent_proposal` is true.
3. Persist results, reusing the existing pending/confirmed lifecycle:
   - For each `relevant_existing`: a `pending` `grouping_link` (`anchor_type`, `anchor_id`). For any matched **child**, also add a pending link to its **parent** (rollup), deduped.
   - For each `proposed_new`: create a `groupings` row with `status='proposed'` (dedup by `(type, name)`; if an active one already exists, link it instead), plus a `pending` link.
4. Return a summary (`suggested`, `proposed`) for the turn response and telemetry. `ModelClient` logs cost/tokens to `model_call_log` automatically.

**Failure handling:** if the model call fails, write a `SystemWarning` and persist nothing for that pass (the question is still created). A deterministic substring fallback MAY be retained behind a flag for offline/dev, but is not the primary path.

**Execution:** runs in the existing background thread that `create_question` already spawns — no added latency on the create response. Cost is one routed model call per question create (acceptable; tracked in telemetry).

### Proposal lifecycle (new-item confirmation)

A `proposed` grouping is suggested-but-not-yet-part-of-the-taxonomy. In the question UI it appears as a pending chip marked **new**:

- **Confirm** the chip → grouping `status: proposed → active` AND its link `status: pending → confirmed`.
- **Dismiss** the chip → delete the link; if the grouping is still `proposed` and unreferenced elsewhere, delete it.

This is the mechanism that lets a general question introduce a general grouping (e.g. `plasticity`) that did not previously exist — the core of the gap fix.

---

## Filter Rollup

`GET /api/research/questions?topic_id={id}` (and its generalized successor) returns questions whose **confirmed** link points to that grouping **or** to any grouping whose `parent_id = id`. The engine resolves `{id} ∪ {direct children}` and filters `grouping_links`. Filtering by a leaf stays exact.

---

## API Surface

Existing question-detail contracts stay stable so the UI does not churn during cutover: `GET /api/research/questions[/{id}]` continues to return `topics: [...]` and `concepts: [...]` arrays with the same fields (now sourced from `groupings` + `grouping_links`).

New / changed:

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/research/groupings?type=&status=` | List groupings with `parent_id` (powers the filter bar and hierarchy view; replaces the raw `SELECT … FROM topics` query in the UI) |
| POST | `/api/research/groupings` | Manually create a grouping (`type`, `name`, `parent_id?`) |
| PATCH | `/api/research/groupings/{id}` | Re-parent (`parent_id`, single-level guard → 422) or change `status` (activate proposed / archive) |

The existing per-question topic/concept confirm/dismiss routes keep their shapes during cutover (mapped onto `grouping_links` operations); a generalized `/questions/{id}/groupings/{grouping_id}` pair MAY replace them afterward.

---

## UI Changes (additive, not a rewrite)

The UI talks to the API, not to tables, so the engine swap is largely invisible to it. Changes:

- **Repoint one query:** `ResearchPanel`'s raw `executeSQL("SELECT id, name FROM topics …")` filter query → `GET /api/research/groupings?type=topic`.
- **Hierarchy / curation view (new, additive):** render groupings of a type with children nested; a control to set/clear a grouping's parent (eligible top-level groupings of the same type). Lives in `ResearchPanel`.
- **Proposal-confirm chips (new, additive):** pending chips for `proposed` groupings show a "new" affordance; confirm activates + links, dismiss removes.
- Existing confirmed badges, pending chips, and the topic filter keep working unchanged because their API shapes are unchanged.

---

## Implementation Phases

Each phase is independently shippable and tested. Legacy tables remain until Phase 5.

**Phase 1 — Unified tables + backfill migration (017).**
Create `groupings` / `grouping_links`. Backfill idempotently from `topics`, `concepts`, and the six join tables: each `topic`/`concept` row → a `groupings` row (preserving name/status); `question_topics`/`question_concepts` → links with `anchor_type='question'`; `paper_*` → `anchor_type='paper'`; `dataset_packet_topics` → `anchor_type='dataset_packet'`; `topic_concepts` → `anchor_type='grouping'`; `research_questions.topic_id` → a confirmed `question` link; `study_notes.topic_id/concept_id` → `anchor_type='study_note'`. A legacy-id→grouping-id mapping (by `(type, name)`) keeps relationships intact. Nothing reads the new tables yet. *Tests:* counts/relationships match legacy; idempotent re-run; rebuild-from-scratch parity (cheap — data is mostly test data).

**Phase 2 — Type-agnostic engine.**
Store functions over the new tables: get/create, link, search, parent/child + rollup, filter, single-level guard. No consumer switched. *Tests:* pure unit tests against the new tables, including invariant guards.

**Phase 3 — Cut over the question workflow + semantic/proposal (closes the gap).**
Repoint `_question_detail`, the question filter, and the suggestion path to the engine; replace `extract_question_topics` with `suggest_groupings` for `topic` and `concept`; add the proposal lifecycle and proposal-confirm UI; seed the `plasticity` parent + the stroke/plasticity hierarchy as data. *Tests:* end-to-end question flow; child→parent rollup; parent-filter descendants; proposal create→confirm→active; mocked `ModelClient` for the matcher. Legacy `question_*` tables left dormant as fallback.

**Phase 4 — Migrate remaining consumers.**
Papers, datasets, `study_notes` anchors, and topic bundles (`claim_store.get_question_bundle`, context orchestrator, research/tutor agents) read the engine instead of legacy tables — one consumer per change, each with tests.

**Phase 5 — Drop legacy.**
Remove `topics`, `concepts`, and the six join tables once grep proves no references. Full suite green.

---

## Testing & Reproducibility

- Per-phase automated tests as above; all run under `uv run pytest tests/ -q` with the standing pass criterion (no new failures beyond `docs/testLog.md`).
- **Idempotency** (CLAUDE.md): re-running migration 017 and re-running `suggest_groupings` on the same question create no duplicate rows.
- Matcher tests mock `ModelClient`; no live model calls in the suite.
- A manual test plan is created/updated under `docs/testsPlans/` **before** each user-visible phase (3 and the UI parts of 4), Prerequisites starting with `uv run pytest tests/ -q`. Manual coverage focuses on the browser hierarchy view, the proposal-confirm flow, and real model-call behavior that automation mocks out.

---

## Relationship to Other Work

- **Supersedes** the topic-hierarchy-only spec; hierarchy is now a `groupings` property.
- **Closes LOG-062**: semantic/agent matching is the Phase 3 matcher.
- **Research Question Phase 1** (`question_topics`/`question_concepts`) is subsumed — its join tables are backfilled in Phase 1 and retired in Phase 5; its manual test plan’s suggestion expectations are replaced by the semantic+proposal flow.

## Open / Deferred

- Semantic matching against new **anchor** types (papers, datasets) — structurally supported, not wired here.
- Additional seeded parents (`neuromodulation`, `rehabilitation`) — left to user curation / agent proposal.
- Replacing per-question topic/concept routes with the generalized `/groupings` link routes — optional cleanup after Phase 4.
- Embedding-based matching — not pursued (LLM matcher chosen).
