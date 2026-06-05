# Learning Plans — Design Spec (build-ready)

**Date:** 2026-06-05
**Author:** Claude (brainstormed with user)
**Epoch:** Research (`src/neurodb/research/`), with shared agent tools (Tutor + Research) and a Study Log UI surface.
**Refines:** `docs/superpowers/specs/2026-06-02-learning-plans-design.md` (feature capture). This spec supersedes that capture's UI placement ("dedicated Plans panel" → Study Log section), creation source (tutor-only → both agents), and adds the proposed→confirmed lifecycle for creation **and** agent updates. Unblocked now that Unified Groupings (Phases 1–5) and Research Question Phase 1 are complete.

---

## Goal

When the NeuroTutor or the Research agent surfaces an interesting topic, the user can explore it in chat and request a **study plan**. The agent proposes a plan; once the user reviews and approves it, the plan becomes a tracked item in the **Study Log panel**, where its reading (papers), groupings, and topics are cross-referenced and progress is tracked. The user can modify or remove plans, or ask either agent to update a plan based on new user or agent discoveries.

## Resolved design decisions

1. **Approval model:** proposed → confirmed, reusing the existing grouping pending/confirmed convention. Agent-created plans are born `proposed`; approval makes them active Study Log items.
2. **Agent updates:** also proposed → confirmed. An agent's changes to an active plan surface as pending step additions/removals the user confirms or dismisses; the active plan is unchanged until then.
3. **Notes integration:** a plan is a **self-contained** Study Log item. Cross-referencing of papers/topics/concepts is via the **unified grouping links**; per-step notes live on the step. Existing `study_notes` are untouched.
4. **Research-question relationship:** independent. A nullable `research_question_id` records provenance; **no** research-question-side UI or lifecycle changes in v1.
5. **Lifecycle modeling:** state lives **on the rows** (`learning_plans.status`, `plan_steps.lifecycle`) — no separate proposals/diff table. Step revisions = remove + add.
6. **Papers resolve on confirm:** read-step papers are queued into Knowledge Library only when the plan (or the pending change) is confirmed, so a dismissed plan leaves **zero** Knowledge Library artifacts.

---

## Data model

No foreign-key constraints are declared on these tables (consistent with the DuckDB-safe convention established in the groupings work — DuckDB rejects `UPDATE` on FK-referenced rows; integrity is enforced in the store layer).

### `learning_plans`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | int PK | |
| `title` | text | Short plan name. |
| `origin_prompt` | text | The topic/ask that generated the plan. |
| `origin_agent` | text | `tutor` \| `research` — which agent proposed it. |
| `origin_session_id` | int, nullable | The chat session it came from (plain indexed int). |
| `research_question_id` | int, nullable | Optional provenance link; no RQ-side behavior in v1. |
| `status` | text | `proposed` \| `active` \| `paused` \| `done`. |
| `created_at` | text (ISO) | |
| `updated_at` | text (ISO) | |

### `plan_steps`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | int PK | |
| `plan_id` | int | Parent plan (plain indexed int). |
| `order_index` | int | Step order within the plan. |
| `step_type` | text | `read` \| `action`. |
| `paper_id` | int, nullable | Set for confirmed `read` steps after resolution. |
| `source_ref` | text (JSON), nullable | For a `proposed` `read` step before resolution: `{title, source_type, topic_context}`. Cleared once `paper_id` is set. |
| `action_text` | text, nullable | Set for `action` steps. |
| `lifecycle` | text | `proposed` \| `confirmed` \| `proposed_removal`. |
| `progress` | text | `todo` \| `in_progress` \| `done` \| `skipped` (meaningful once `confirmed`). |
| `note` | text, nullable | Free-text per-step note; lives on the step. |
| `created_at` | text (ISO) | |
| `updated_at` | text (ISO) | |

Indexes: `learning_plans(status)`; `plan_steps(plan_id)`, `plan_steps(lifecycle)`.

### Categorization / cross-reference
A plan is a new groupable entity: `learning_plan` is added to the grouping **type registry's** valid `anchor_type` set, and topics/concepts attach to plans through the **existing `grouping_links`** table (`anchor_type='learning_plan'`, `anchor_id=plan_id`, `status` pending/confirmed). This powers "this paper/topic appears in N plans." Read-step papers keep their own existing grouping links.

### Derived values
- **% complete** = confirmed `done` ÷ confirmed non-`skipped` steps (proposed steps excluded from both).
- **Where am I** = first `confirmed` step whose `progress` is not `done`/`skipped`.

---

## Migration

**Migration 022** (`_migration_022_learning_plans`): `CREATE TABLE IF NOT EXISTS` for `learning_plans` and `plan_steps` plus their indexes. New install only — no backfill. Registered in `_MIGRATIONS` under key `22` and re-exported through `src/neurodb/db/__init__.py` (the package re-export layer over the flat `db.py`). The ORM models go in `schema.py`.

---

## Agent tools (shared, registered on both agents)

Defined once in the Research epoch (e.g. `src/neurodb/research/learning_plans.py` store + a thin tool wrapper) and registered in **both** `tutor_agent.py` and `research_agent.py`. Tools run in-process and call the store directly (like `queue_source` / `record_research_question`), not over HTTP. Tool schemas are Groq-safe (every object declares `properties` + `required`).

- **`propose_learning_plan(title, origin_prompt, steps[])`**
  - `steps[]`: each is `{type:'read', source:{title, source_type, topic_context}}` or `{type:'action', action_text}`.
  - Persists `learning_plans` `status='proposed'` (`origin_agent` from the calling agent) and `plan_steps` all `lifecycle='proposed'`. `read` steps store `source_ref` JSON; **no paper is queued yet**.
  - Calls `run_suggest_groupings(anchor_type='learning_plan', anchor_id=plan_id, anchor_text=title+"\n"+origin_prompt, gtypes=('topic','concept'))` so proposed topic/concept chips attach from creation (fail-closed, same as questions).
  - Returns a summary (plan id, step count, suggested groupings).
- **`update_learning_plan(plan_id, add_steps[]?, remove_step_ids[]?)`**
  - Inserts `add_steps` as `lifecycle='proposed'`; flags `remove_step_ids` (must be `confirmed`) as `proposed_removal`. Never alters confirmed steps' `progress`. Returns the pending-change summary. (Retitle is a user action via PATCH, not an agent-proposed change — keeps the proposed/confirm gate to step structure only.)

## Store layer (`src/neurodb/research/learning_plans.py`)

Pure functions over the tables, no FK reliance:
- `propose_plan(engine, *, title, origin_prompt, origin_agent, steps, origin_session_id=None, research_question_id=None) -> dict`
- `propose_plan_update(engine, *, plan_id, add_steps=None, remove_step_ids=None) -> dict`
- `confirm_plan(engine, plan_id) -> dict` — `proposed`→`active`; all `proposed` steps→`confirmed`; for each newly-confirmed `read` step, resolve `source_ref` via the existing `queue_source`/paper-dedup path to set `paper_id` and clear `source_ref`.
- `confirm_pending_changes(engine, plan_id) -> dict` — on an active plan: `proposed`→`confirmed` (resolving read papers), `proposed_removal`→deleted.
- `dismiss_plan(engine, plan_id) -> bool` — delete a `proposed` plan and its steps; no KL side effects.
- `dismiss_pending_changes(engine, plan_id) -> dict` — delete `proposed` steps; revert `proposed_removal`→`confirmed`.
- `set_step_progress(engine, step_id, progress, note=None)`; `confirm_step` / `dismiss_step` for single proposed steps.
- `update_plan(engine, plan_id, *, title=None, status=None, step_order=None)` — user edits (retitle/reorder/pause/done).
- `delete_plan(engine, plan_id) -> bool`.
- `list_plans(engine, status=None) -> list[dict]`; `get_plan(engine, plan_id) -> dict` (steps ordered, lifecycle+progress, grouping links, `% complete`, `appears_in_n_plans` for shared papers/topics).

Read-step paper resolution reuses the existing dedup path so the same source already in the library is **linked, not duplicated** (idempotent).

---

## API (React UI) — added to the research router

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/research/plans?status=` | List plans (title, status, % complete, step counts, topic chips, pending-change count). |
| GET | `/api/research/plans/{id}` | Plan detail (ordered steps w/ lifecycle+progress, grouping links, "appears in N plans"). |
| POST | `/api/research/plans/{id}/confirm` | Confirm a `proposed` plan → `active` (422 if the plan is not `proposed`). Maps to `confirm_plan`. |
| POST | `/api/research/plans/{id}/confirm-changes` | Confirm an active plan's pending step changes. Maps to `confirm_pending_changes`. |
| POST | `/api/research/plans/{id}/dismiss-changes` | Dismiss only pending changes (proposed steps deleted; `proposed_removal`→`confirmed`). |
| PATCH | `/api/research/plans/{id}` | Retitle, reorder, set `paused`/`done`. |
| PATCH | `/api/research/plans/{id}/steps/{step_id}` | Set progress, edit note, or confirm/dismiss one proposed step. |
| DELETE | `/api/research/plans/{id}` | Remove a plan. |

Topic/concept chip confirm/dismiss reuse the **existing** generalized grouping-link routes with `anchor_type='learning_plan'`.

---

## End-to-end flow

1. Tutor or Research agent surfaces a topic in chat; the user explores via normal chat; the user asks for a study plan.
2. Agent calls `propose_learning_plan`; plan + steps persist `proposed`; topic/concept chips suggested.
3. A **"Proposed — needs review"** plan appears in the Study Log Plans section.
4. **Confirm** → `status='active'`, steps `confirmed`, read-step papers queued/deduped into Knowledge Library, chips confirmable. **Dismiss** → plan deleted, no side effects.
5. Later the user asks an agent to update the plan → proposed adds / `proposed_removal` flags surface as pending on the active plan → the user confirms or dismisses (per-step or bulk).
6. The user tracks progress per step (and notes), pauses/finishes/deletes plans, and sees cross-plan shared papers/topics.

---

## UI — Study Log panel

- The **Study Log panel gets a "Plans" section** alongside the existing notes/tags view; approved plans live here.
- **Plan list:** cards with title, status badge (Proposed/Active/Paused/Done), % complete bar, step count, topic/concept chips. Proposed plans show **Confirm/Dismiss**; active plans with pending agent changes show an **"N pending changes"** badge.
- **Plan detail** (expand/drawer): ordered steps — `read` steps link to the paper in Knowledge Library, `action` steps show their text; each confirmed step has a progress control and a note field. Proposed steps render pending (Confirm/Dismiss, single or bulk); `proposed_removal` steps render struck-through with Keep/Remove. Topic chips reuse the existing confirm/dismiss chip component.
- **Cross-reference (v1, minimal):** plan detail and a paper/topic surface **"appears in N plans."** Full multi-plan dashboard deferred.

---

## Scope

**v1:** the two tables + migration 022; `learning_plan` grouping anchor type; `propose_learning_plan` + `update_learning_plan` on both agents; proposed→confirmed lifecycle (plan + steps, `proposed_removal`); read-paper resolution on confirm; per-step progress + notes; % complete; the API routes; Study Log Plans section + detail + chips; minimal "appears in N plans."

**Deferred (YAGNI):** multi-plan progress dashboard; semantic "plans related to this plan"; plan-activity→`study_notes` bridge; bidirectional plan↔question views / RQ lifecycle reshape; typed `action`-step outcomes (free-text note only in v1).

---

## Testing & reproducibility

- **Unit (store):** `propose_plan` persists all-`proposed` with `source_ref` set and no paper queued; `confirm_plan` flips plan+steps to active/confirmed and resolves read papers via dedup (idempotent — existing source linked, not duplicated); `dismiss_plan` deletes with **zero** Knowledge Library artifacts; `propose_plan_update` adds `proposed` / flags `proposed_removal`; `confirm_pending_changes` / `dismiss_pending_changes`; `% complete` derivation (excludes `skipped` and `proposed`); progress transitions; `learning_plan` grouping links (proposed→confirmed + parent rollup).
- **Idempotency:** re-running `propose`/`confirm` creates no duplicate steps or papers.
- **Integration:** tutor chat → `propose_learning_plan` → proposed rows → confirm → active + papers in Knowledge Library; research-agent path; update → pending → confirm.
- **API + frontend:** each route's behavior; Plans list/detail render, confirm/dismiss, progress controls, pending-changes badge. Matcher reached via the plan tools uses mocked `ModelClient` (no live calls in the suite).
- **Manual test plan** created in `docs/testsPlans/` **before** implementation (CLAUDE.md), first prerequisite `uv run pytest tests/ -q` (no new failures beyond `docs/testLog.md`), focused on the live chat→propose→Study-Log-review→confirm→track flow and agent-driven update across **both** agents.

---

## Status-doc sync (on completion)

Move this spec + the eventual implementation plan + manual test plan into the `projectStatus.md` reference table; set Active focus to Learning Plans while in flight; on sign-off, mark complete and archive the manual plan. Remove the "learning plans" item from Deferred / Upcoming when work starts.
