# Groupings Phase 3 — Question Cutover + Semantic/Proposal Matcher — Design Spec

**Date:** 2026-06-01
**Author:** Claude (brainstormed with user)
**Status:** Complete — delivered through Phases 3a/3b and final signed off 2026-06-04
**Parent spec:** `docs/superpowers/specs/2026-06-01-unified-groupings-taxonomy-design.md` (this details that spec's Phase 3)
**Builds on:** Phase 1 (unified tables + backfill, commit `b9bb250`) and Phase 2 (type-agnostic engine `grouping_store.py`)
**Closes:** LOG-062 (semantic / agent-based grouping suggestion)

> This is the phase that closes the user's gap. After Phase 3, a general or off-domain question gets meaningful suggestions, a general grouping that does not yet exist (`plasticity`) can be proposed and confirmed, and a child match rolls up to its parent.

---

## Scope & Packaging

Phase 3 is delivered as **two independently shippable plans sharing this one spec**:

- **Phase 3a — Backend cutover (server-side gap closure).** The semantic/proposal matcher, the `agent.extract.groupings` task type, the `/api/research/groupings` routes, the proposal lifecycle wired onto the existing per-question routes, the `_question_detail` / question-filter cutover to the engine, and the hierarchy seed migration `018`. Fully testable via API + mocked `ModelClient`; the gap is closed server-side here.
- **Phase 3b — UI (additive).** Proposal-confirm "new" chips, the hierarchy / curation view, and repointing the one raw `executeSQL` filter query to the new route. No new backend behavior.

3a lands and is verified first; 3b consumes only stable, already-shipped API shapes.

### Cutover decision: full cutover (no dual-write)

`create_question` stops writing `question_topics` / `question_concepts`; suggestions and links are written to and read from `grouping_links` only. Legacy `question_*` tables keep their Phase-1-backfilled rows as a **dormant fallback** (not written, not read) until Phase 5 drops them. Rollback is "revert the code" — `grouping_links` already holds the full history from the Phase 1 backfill. This avoids dual-write drift and matches the parent spec's "legacy left dormant" wording.

---

## Contract-Stability Strategy (the key idea)

The frontend and the existing API shapes do not change in 3a. The trick: **the `topic_id` and `concept_id` fields in the existing contracts become grouping ids** (of type `topic` / `concept` respectively).

- `_question_detail` sources `topics[]` from `grouping_links` where `anchor_type='question'` joined to `groupings` of `type='topic'`, returning `topic_id = grouping.id`, `topic_name = grouping.name`, `status = link.status`. Same for `concepts[]` / `type='concept'`.
- The existing `PATCH/DELETE /questions/{id}/topics/{topic_id}` and `.../concepts/{concept_id}` routes treat the path id as a **grouping id** and operate on `grouping_links` via `update_link_status` / `unlink_grouping`.
- The `?topic_id=` filter on `GET /questions` treats the value as a grouping id and applies `resolve_filter_ids` (parent → self + children) for hierarchy rollup.
- The React chips key on `t.topic_id` / `c.concept_id` and call the same routes — they keep working with zero change because the ids are still opaque integers to the UI.

One additive field closes the loop for proposals (below). No breaking change ships in 3a.

---

## Phase 3a — Backend

### 1. New task type

Add to `neurodb_models.toml` (the existing unused `agent.extract` stays as-is; this is a distinct, more specific type so routing/telemetry are unambiguous):

```toml
[tasks."agent.extract.groupings"]
tier = "standard"
max_tokens = 1024
```

`tier = standard` per the parent spec (the matcher must reason, not just summarize). Routing/telemetry keys must match the `task_type` passed to `record_model_call`.

### 2. The matcher — `suggest_groupings`

New module `src/neurodb/research/grouping_matcher.py`, modeled exactly on `research/hypothesis_review.py` (system prompt + single forced tool + `record_model_call` + tool-input parse).

**Signature:**
```python
def suggest_groupings(
    engine: Engine,
    *,
    anchor_type: str,
    anchor_id: int,
    anchor_text: str,
    gtype: str,
    model_client: ModelClient,
    model: str,
    model_provider: str,
    max_tokens: int,
) -> dict
```

`model_client` / `model` / `model_provider` / `max_tokens` are injected by the caller from a resolved `ModelRoute` — exactly how `run_hypothesis_review` is called (`research.py:393`). This keeps the matcher unit-testable with a fake `ModelClient` and no live calls.

**Flow:**
1. Load active groupings of `gtype` via `grouping_store.list_groupings(session, gtype=gtype, status="active")` (id, name, parent_id, description).
2. Build the forced-tool call. **One** tool, `submit_groupings`, called once. Groq-safe schema — every object declares `properties` + `required`, never a bare `{"type":"object"}` (per known Groq strict-schema behavior, memory `feedback_groq_tool_schema`):

```python
_SUBMIT_GROUPINGS_TOOL = {
    "name": "submit_groupings",
    "description": "Record which existing groupings are relevant to the text and propose any new ones. Call exactly once.",
    "input_schema": {
        "type": "object",
        "properties": {
            "relevant_existing": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "reason"],
                },
            },
            "proposed_new": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "parent_name": {"type": ["string", "null"]},
                    },
                    "required": ["name", "parent_name"],
                },
            },
        },
        "required": ["relevant_existing", "proposed_new"],
    },
}
```

3. Call `model_client.create_message(model=..., max_tokens=..., system=_SYSTEM_PROMPT, tools=[model_client.format_tool(_SUBMIT_GROUPINGS_TOOL)], messages=[{"role":"user","content": <anchor_text + candidate list as JSON>}], tool_choice="required")`.
4. `record_model_call(engine, task_type="agent.extract.groupings", provider=model_provider, model=model, mode="neuro_research", response=response, iteration=1, elapsed_ms=...)`.
5. Persist (one DB session), reusing the engine's link lifecycle:
   - For each valid `relevant_existing.id` that maps to a real active grouping of `gtype`: `link_grouping(session, gid, anchor_type, anchor_id, status="pending")`. For any matched **child** (`parent_id` not null), also `link_grouping(parent_id, ..., status="pending")` — rollup, deduped (link is idempotent).
   - For each `proposed_new` when `GROUPING_TYPES[gtype].allow_agent_proposal` is true: `get_or_create_grouping(session, gtype, name, status="proposed")`; if an **active** one already exists with that name, link it as existing instead (no new proposed row). Then `link_grouping(session, gid, anchor_type, anchor_id, status="pending")`. `parent_name` is recorded but **not** auto-parented in 3a (parenting is a curated action; seeded hierarchy covers the known cases — see §5).
6. Return `{"anchor_type", "anchor_id", "gtype", "suggested": [...names], "proposed": [...names]}` for telemetry/logging.

The matcher is **called twice per question** — once with `gtype="topic"`, once with `gtype="concept"` — from the cutover background thread (§4). Two routed model calls per create; acceptable and tracked (parent spec).

**Fail closed (no fallback).** A thin caller wrapper resolves the route and runs the matcher inside `try/except (RoutingError, KeyError, Exception)`. On failure it calls `record_system_warning(engine, warning_type="grouping_match_failed", severity="warning", task_type="agent.extract.groupings", message=...)` and persists **nothing** for that pass. The question is already created and is fully usable; the human fallback is manual tagging via the grouping API/UI. No substring fallback is reintroduced.

### 3. `/api/research/groupings` routes

New router section in `routes/research.py` (thin wrappers over `grouping_store`; `GroupingHierarchyError` → HTTP 422). New request/response schemas in `api/schemas/research.py`.

| Method | Route | Body / Query | Maps to |
|---|---|---|---|
| GET | `/api/research/groupings` | `?type=&status=` | `list_groupings(session, gtype=type, status=status)` |
| POST | `/api/research/groupings` | `{type, name, parent_id?, description?}` | `get_or_create_grouping` (+ `set_parent` if `parent_id`) |
| PATCH | `/api/research/groupings/{id}` | `{parent_id?: int\|null, status?: str}` | `set_parent` (422 on invariant) and/or status change |

`GroupingItem` response: `{id, type, name, parent_id, status, description}`. The PATCH `status` field is how a `proposed` grouping is activated or any grouping archived from the curation UI.

### 4. Question-flow cutover

In `routes/research.py`:

- **`_question_detail`** (line 41): replace the `QuestionTopic`/`QuestionConcept` joins with `get_groupings_for_anchor(session, "question", question_id)`, partitioned by `g["type"]` into `topics[]` (type=topic) and `concepts[]` (type=concept). `topic_id = g["id"]`, `topic_name = g["name"]`, `status = g["link_status"]`, **`proposed = (g["grouping_status"] == "proposed")`**. *3a extends the Phase 2 `get_groupings_for_anchor` to also return each grouping's own `status` as `grouping_status` in its dict (a small additive change, covered by a store unit test) so `proposed` is derivable without a second query.*
- **`create_question`** (line 160): the background `_extract` thread resolves a route and calls the matcher for both types:
  ```python
  def _extract():
      from neurodb.config.provider_factory import build_provider_clients
      from neurodb.config.task_router import TaskRouter
      from neurodb.research.grouping_matcher import run_suggest_groupings  # fail-closed wrapper
      run_suggest_groupings(engine, anchor_type="question", anchor_id=question_id,
                            anchor_text=body.question, gtypes=("topic", "concept"))
  ```
  (`run_suggest_groupings` does the route resolution per type, the try/except fail-closed, and the two matcher calls. `extract_question_topics` is no longer called.)
- **`get_questions`** `?topic_id=` filter (line 129): resolve `resolve_filter_ids(session, topic_id)` and filter questions whose **confirmed** `grouping_links` (`anchor_type='question'`) point to any id in that set.
- **Per-question routes** (`POST/PATCH/DELETE .../topics/{id}` and `.../concepts/{id}`): re-point onto `grouping_links`:
  - `POST .../topics` body `{topic_id}` (a grouping id) → `link_grouping(session, topic_id, "question", question_id, status="confirmed")`.
  - `PATCH .../topics/{topic_id}` `{status}` → **proposal-aware**: `update_link_status(session, topic_id, "question", question_id, status)`; when `status == "confirmed"` and the grouping is `proposed`, also flip the grouping to `active` (PATCH the grouping status). Returns 404 if no link.
  - `DELETE .../topics/{topic_id}` → `unlink_grouping(...)`; then if the grouping is still `proposed` and has no remaining links anywhere, delete the grouping (proposal cleanup). 404 if no link.
  - Concept routes mirror this with `gtype='concept'`.

These remappings live behind the existing route signatures, so the contract and the UI are unchanged in 3a except for the additive `proposed` field.

### 5. Hierarchy seed — migration `018`

`_migration_018_seed_grouping_hierarchy(conn)` — additive, idempotent (registered as `18` in `_MIGRATIONS`):

1. Ensure a top-level `topic` grouping named `plasticity` exists (`INSERT ... WHERE NOT EXISTS` by `(type='topic', name='plasticity')`; `status='active'`, timestamps = run time).
2. Set `parent_id` on the seed children by resolving names → grouping ids within `type='topic'` and issuing `UPDATE groupings SET parent_id = :pid, updated_at = :now WHERE type='topic' AND name = :child AND (parent_id IS NULL OR parent_id <> :pid)`.

Seed mapping (carried forward from the user-confirmed mapping in the superseded topic-hierarchy spec):

| Parent (topic) | Children (existing topic names) |
|---|---|
| **plasticity** (created here) | neuroplasticity, circuit plasticity, interhemispheric plasticity, cortical remapping, maladaptive reorganization, interhemispheric competition, interhemispheric inhibition, transcallosal inhibition |
| **stroke** (existing) | stroke recovery, stroke rehabilitation, stroke severity, peri-infarct cortex |

Children whose names are absent are skipped silently. Idempotent: re-running creates no duplicate `plasticity` and re-sets identical `parent_id` values. `UPDATE` on `groupings` is safe — no FK references the table (the whole point of the no-FK design; DuckDB allows it).

### 6. 3a tests (all automated, `uv run pytest tests/ -q`)

- **Matcher (mocked `ModelClient`):** a fake client returning a `submit_groupings` tool call. Asserts pending links for `relevant_existing`; child match also links parent (rollup); `proposed_new` creates a `proposed` grouping + pending link; an existing-active name in `proposed_new` links instead of duplicating; `allow_agent_proposal=False` (simulated type) ignores proposals. No live model calls.
- **Fail-closed:** route resolution raising `RoutingError` → a `SystemWarning` row written, zero links/groupings created, question still exists.
- **`_question_detail` / filter cutover:** detail returns engine-sourced topics/concepts with correct `status` and `proposed`; `?topic_id=parent` returns a question whose confirmed link is to a child; `?topic_id=leaf` is exact.
- **Proposal lifecycle via routes:** PATCH confirm on a proposed-grouping link flips grouping `proposed→active` and link `pending→confirmed`; DELETE dismiss removes the link and deletes the now-orphan proposed grouping; dismiss of an active grouping's link leaves the grouping intact.
- **`/groupings` routes:** GET filters by type/status; POST creates (+ parent); PATCH re-parent invariant → 422; PATCH status activates/archives.
- **Migration 018:** creates `plasticity`, sets seed parents, idempotent re-run; absent children skipped.

A manual test plan for 3a is created under `docs/testsPlans/` before implementation (Prerequisites start with `uv run pytest tests/ -q`), focused on a **real** model call (the one thing automation mocks) — create a question, observe pending chips appear from the live matcher, including a proposed "new" grouping — plus the fail-closed path with providers disabled.

---

## Phase 3b — UI (additive)

In `frontend/src/pages/ResearchPanel.tsx` and the API client/types:

- **Repoint the filter query** (`ResearchPanel.tsx:660`): replace `api.executeSQL("SELECT id, name FROM topics WHERE status='active' ORDER BY name")` with a typed `api.listGroupings({ type: "topic", status: "active" })` → `GET /api/research/groupings?type=topic&status=active`. (Removes the last raw-SQL read in this panel.)
- **Proposal "new" chips:** the pending-chip renderer (lines ~296–308) reads the additive `proposed` boolean on each topic/concept link; when true, render a small **new** badge alongside the dashed chip. Confirm (✓) and dismiss (✕) call the *same* existing mutations (`confirmQuestionTopic` / `dismissQuestionTopic`, etc.) — the backend already activates/cleans up the proposed grouping. No new mutation needed.
- **Hierarchy / curation view (new, additive):** a small section in `ResearchPanel` listing topic groupings with children nested, and a control per grouping to set/clear its parent (dropdown of eligible top-level same-type groupings + "No parent"), calling `PATCH /api/research/groupings/{id}` with `{parent_id}`. 422 surfaces as an inline message. Reuses the existing `@tanstack/react-query` + `api` patterns.
- **Types:** add `proposed?: boolean` to `QuestionTopicLink` / `QuestionConceptLink` in `frontend/src/api/types.ts`; add `GroupingItem` and the `listGroupings` / `createGrouping` / `patchGrouping` client functions in `client.ts`.

### 3b tests / verification

- A manual test plan under `docs/testsPlans/` (created before 3b implementation): the browser proposal-confirm flow (a "new" chip appears, confirming it persists and the grouping becomes active/filterable), the hierarchy view re-parent action and its 422 path, and the parent-filter returning child-tagged questions. Automated coverage of the underlying logic already exists from 3a; the manual plan focuses on browser wiring and live server/DB integration, per CLAUDE.md.

---

## Migration / Rollout Notes

- `init_db` registers `018` and runs it on next startup; existing DBs pick up the seed automatically. Purely additive.
- Phase 3a is mergeable before 3b: the `proposed` field and `/groupings` routes are additive; the old UI ignores the new field and keeps working.
- Legacy `question_topics` / `question_concepts` remain present but unwritten/unread after 3a; Phase 4 migrates the remaining consumers (papers, datasets, notes, bundles) and Phase 5 drops the legacy tables.

## Open / Deferred (unchanged from parent spec)

- Semantic matching against new **anchor** types (papers, datasets) — Phase 4+ / future.
- Auto-parenting from the matcher's `parent_name` hint — recorded but not applied; revisit if curation proves tedious.
- Generalized `/questions/{id}/groupings/{grouping_id}` routes replacing the per-type routes — optional cleanup after Phase 4.
- Four-axis question categorization as grouping types — deferred to the end of the research-question implementation, per the parent spec.
