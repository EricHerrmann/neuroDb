# Topic Taxonomy Hierarchy — Design Spec

**Date:** 2026-06-01
**Author:** Claude (brainstormed with user)
**Status:** Draft — awaiting user review
**Related:** LOG-062 (semantic topic suggestion — separate enhancement), `docs/researchQuestionDesignClaude.md` / `docs/researchQuestionDesignCodex.md` (neither addresses topic-taxonomy generality)

---

## Problem

The `topics` table is a flat list of ~27 granular terms (e.g. `neuroplasticity`, `circuit plasticity`, `interhemispheric plasticity`, `cortical remapping`) with no general/parent category and no `plasticity` topic at all. Question→topic suggestion matches a question's text against topic names; with only granular topics and no general buckets, general questions cannot be tagged to a general topic. The phased research-question designs assume the existing taxonomy is adequate and never revisit its granularity — so this gap is unowned. This spec adds a parent/child topic hierarchy and makes question→topic suggestion and filtering hierarchy-aware.

## Goals

- A topic can own child topics via a parent relationship (e.g. `plasticity` owns `neuroplasticity`, `circuit plasticity`, …; `stroke` owns `stroke recovery`, `stroke rehabilitation`, …).
- When a question's text matches a child topic, both the child and its parent are suggested.
- Filtering the question list by a parent topic returns questions tagged to that parent OR any of its direct children.
- The user can view the hierarchy and re-parent topics from the UI.

## Non-Goals

- **Semantic / agent-based topic matching.** The underlying match stays literal substring (case-insensitive, whole topic name as substring of question text). Replacing it with semantic matching is tracked separately as **LOG-062** and is explicitly out of scope here.
- **Arbitrary-depth hierarchy.** Single-level nesting only (see Data Model).
- **Concept hierarchy.** This spec covers `topics` only, not `concepts`.
- **ChromaDB / semantic indexing of topics.** Pure relational change.

---

## Data Model

Add one column to the `Topic` model (`schema.py`):

```
parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
```

- **Plain indexed integer column, NO `ForeignKey` constraint.** `topics` rows are referenced by many tables (`question_topics`, `paper_topics`, `topic_concepts`, `dataset_packet_topics`, …). DuckDB rejects `UPDATE` on any column of an FK-referenced row, and re-parenting requires updating `parent_id`. A formal self-FK would make re-parenting impossible — the same constraint that drove migration 012 to rebuild tables without FK constraints (LOG-037). The column carries the relationship by convention; integrity is enforced in application code.
- `parent_id IS NULL` ⇒ top-level topic.

### Single-level nesting invariant

A topic may have at most one parent, and **a parent must itself be top-level** (no grandchildren). Enforced in the application layer:

- Setting `parent_id = P` on topic `C` is rejected if topic `P` already has a non-null `parent_id` (would create a grandchild).
- Setting `parent_id` on a topic that already has children is rejected (would turn a parent into a child).
- A topic cannot be its own parent (`C.parent_id != C.id`).

These guards live in the topic-store update function (§Curation) and the PATCH route returns HTTP 422 on violation.

---

## Seed Migration (017)

`_migration_017_topic_parent_hierarchy(conn)` — additive and idempotent:

1. `ALTER TABLE topics ADD COLUMN parent_id INTEGER` (try/except for re-run).
2. `CREATE INDEX IF NOT EXISTS ix_topics_parent_id ON topics (parent_id)`.
3. Ensure a top-level `plasticity` topic exists (`INSERT … WHERE NOT EXISTS` by name; `status='active'`, timestamps set to migration run time).
4. Set `parent_id` on the seed children by resolving parent/child topic names to ids and issuing `UPDATE topics SET parent_id = :pid WHERE name = :child AND parent_id IS DISTINCT FROM :pid`.

Idempotency: re-running creates no duplicate `plasticity`, and re-sets the same `parent_id` values (no-op on second run). Children whose names are absent are skipped silently.

### Seed mapping (user-confirmed)

| Parent | Children (existing topic names) |
|---|---|
| **plasticity** (created by this migration) | neuroplasticity, circuit plasticity, interhemispheric plasticity, cortical remapping, maladaptive reorganization, interhemispheric competition, interhemispheric inhibition, transcallosal inhibition |
| **stroke** (existing topic) | stroke recovery, stroke rehabilitation, stroke severity, peri-infarct cortex |

All other existing topics remain top-level (`parent_id = NULL`) and are curated later via the UI.

---

## Matching / Rollup Behavior

In `extract_question_topics` (`db/topic_store.py`), after the existing substring-match step builds the set of matched topics:

1. Keep the current literal-substring matching against all active topics (unchanged).
2. For each matched topic that has a non-null `parent_id`, also include the parent topic in the suggestion set (dedup against already-matched topics and against existing pending/confirmed links).
3. Persist parent suggestions as `status='pending'` `question_topics` rows, exactly like child suggestions. Existing dedup (the `WHERE NOT EXISTS` / unique index on `(question_id, topic_id)`) prevents duplicates.

Result:
- Question text containing `circuit plasticity` → pending chips for `circuit plasticity` **and** `plasticity`.
- Question text containing `plasticity` (now a real topic) → matches `plasticity` directly via substring; if no child name also appears, only `plasticity` is suggested.
- Question text containing `peri-infarct cortex` → matches that child, rolls up to `stroke` even though "stroke" is not a substring of the text.

The returned summary dict's `suggested_topics` includes the rolled-up parents so the turn response count is accurate.

---

## Filter Rollup

Extend `GET /api/research/questions?topic_id={id}` (`routes/research.py`):

- When `topic_id` resolves to a topic, match questions whose **confirmed** `question_topics` link (matching the existing filter, which already restricts to `status='confirmed'`) points to that topic **or** to any topic whose `parent_id = topic_id`.
- Implemented as: resolve the set `{topic_id} ∪ {child ids where parent_id = topic_id}` and filter `question_topics.topic_id IN (...)`.
- Filtering by a child id stays exact (a leaf has no children, so the set is just itself).

The frontend topic filter bar (`ResearchPanel.tsx`) is structurally unchanged; selecting a parent simply returns more questions. (Optional, low priority: visually nest children under parents in the filter bar — deferred unless requested.)

---

## Curation Surface

### API (`routes/research.py`, or a small `routes/topics.py` under `/api/research`)

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/research/topics` | List active topics with `id`, `name`, `parent_id`, `status` |
| PATCH | `/api/research/topics/{id}` | Body `{parent_id: int | null}`; set/clear parent; enforces single-level invariant; 422 on violation |

### topic_store

`set_topic_parent(session, topic_id, parent_id)`:
- `parent_id=None` clears the parent.
- Validates: target exists; not self-parent; proposed parent is top-level; target has no children. Raises a typed error the route maps to 422.

### UI

A lightweight **Topic Hierarchy** view (within ResearchPanel, near the existing topic filter, or a small dedicated section): renders parents with their children nested, and provides a control per topic to set or clear its parent (dropdown of eligible top-level topics + "No parent"). Reuses existing fetch/mutation patterns (`@tanstack/react-query` + `api` client). No new route required.

---

## Testing

Automated (`uv run pytest tests/ -q`), all new:

- **Schema/migration:** migration 017 adds `parent_id`; creates `plasticity`; sets seed `parent_id` values; re-running is a no-op (no duplicate `plasticity`, same parents). Absent child names are skipped.
- **Invariant guard:** `set_topic_parent` rejects grandchild (parent already has a parent), rejects parenting a topic that has children, rejects self-parent; clearing parent works.
- **Rollup matching:** `extract_question_topics` for a question containing a child topic name persists pending rows for both child and parent; a parent-only match persists only the parent; a child whose parent is not a substring (peri-infarct cortex → stroke) still rolls up.
- **Filter rollup:** `GET /questions?topic_id=parent` returns a question tagged only to a child; `?topic_id=child` returns only child-tagged questions.
- **Idempotency:** re-running the migration and re-suggesting the same question create no duplicate rows.

Manual test plan: update `docs/testsPlans/manualTestPlan_research_question_phase1.md` (or add a focused plan) before implementation, per CLAUDE.md — covering the browser hierarchy view, re-parent action, and the parent-filter behavior. Prerequisites section must start with `uv run pytest tests/ -q` and the standard pass criterion.

---

## Migration / Rollout Notes

- `init_db` registers `017` in `_MIGRATIONS` and runs it on next startup; existing DBs pick it up automatically.
- No data is destroyed; the change is purely additive plus `parent_id` updates on the seeded children.
- `Base.metadata.create_all` (via the model column) and the migration are reconciled: the model gains `parent_id`; the migration handles existing DBs. New DBs get the column from the model and the seed from the migration.

## Open / Deferred

- Visual nesting of children in the filter bar — deferred.
- `neuromodulation` / `rehabilitation` as additional parents (rTMS, optogenetics, electrical stimulation; neurorehabilitation, CIMT) — left to user curation via the UI; not seeded.
- Semantic matching — LOG-062, separate.
