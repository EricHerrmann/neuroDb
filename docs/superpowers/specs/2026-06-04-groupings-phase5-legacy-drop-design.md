# Groupings Phase 5 — Legacy Table Retirement — Design Spec

**Date:** 2026-06-04
**Author:** Claude (brainstormed with user)
**Parent spec:** `docs/superpowers/specs/2026-06-01-unified-groupings-taxonomy-design.md` (Phase 5 — "Drop legacy")
**Status:** Complete — implemented and signed off 2026-06-04

---

## Problem

The unified groupings migration is complete through Phase 4: every live consumer is meant to read and write `groupings` / `grouping_links` instead of the legacy `topics`, `concepts`, and their six join tables. The legacy tables and their ORM models still exist as a safety net. Phase 5 removes them so the codebase has a single categorization model.

Two facts shape the work:

- **The DB is mostly disposable test data.** There is no long-term value in preserving historical rows at this time. This removes backfill-idempotency and rollback pressure from the design.
- **A few live stragglers still touch legacy tables/models.** They must be cut over before deletion, or the "grep proves no references" gate cannot pass.

## Decisions (locked)

- **Plan and execute fully now** — do not wait on Groupings Phase 4 manual sign-off (T4–T7).
- **Hard `DROP`** via a new migration. No rename-then-drop intermediate. Irreversible in place; acceptable because data is disposable and migrations rebuild a fresh DB.
- **Defer dead-column removal** (`research_questions.topic_id`, `study_notes.topic_id` / `concept_id`). Dropping them needs a DuckDB table rebuild (migration-012 pattern) for little benefit; leave them as harmless unused columns.

---

## The critical ordering risk

The DB bootstraps via `Base.metadata.create_all(engine)` (`src/neurodb/db.py:805`) **and then** runs migrations `1 → N` in order. The legacy tables exist today **only because their ORM models cause `create_all` to create them**; migration 017 then backfills `FROM topics …` with **no existence guard** (`src/neurodb/db.py:510`).

This produces two failure modes a naive drop would hit:

1. **Remove the models, leave 017 as-is** → on a fresh DB the legacy tables never get created, so 017's `FROM topics` backfill crashes and the app/test suite fails to initialize.
2. **Keep the models, drop the tables in a migration** → `create_all` runs *before* migrations on every startup and re-creates the empty legacy tables; the drop migration is already marked applied, so it never fires again → zombie empty tables resurrect on the next boot.

**Resolution:** the ORM models **must** be removed, **and** migration 017's backfill must tolerate the legacy tables being absent.

Because the data is disposable, the chosen fix is the simplest correct one: **guard the legacy-backfill block in migration 017 with a table-existence check** (e.g. `has_table(conn, "topics")`). On a fresh DB the legacy tables are gone → backfill is skipped (nothing to migrate, correct). On any DB that still has legacy rows the guard passes and backfill runs unchanged. The `groupings` / `grouping_links` `CREATE TABLE IF NOT EXISTS` statements stay unconditional.

> Migration 017 currently reads `topics`, `concepts`, `question_topics`, `question_concepts`, `paper_topics`, `paper_concepts`, `topic_concepts`, `dataset_packet_topics` (plus surviving `study_notes` / `research_questions` columns). `question_topics` / `question_concepts` are created by migration 016, but their backfill `JOIN`s `topics` / `concepts`, so the single `topics`-existence guard correctly gates the entire legacy-backfill block.

---

## Scope — changes

### 1. Migration 017 (edit — make backfill absence-tolerant)
Wrap the legacy-backfill statements in a `has_table(conn, "topics")` guard so they no-op when the legacy tables are absent. Leave the `groupings` / `grouping_links` creation unconditional. Idempotent and behavior-preserving for DBs that still hold legacy data.

### 2. Migration 021 (new — hard drop)
`DROP TABLE IF EXISTS` for all eight legacy tables: `topics`, `concepts`, `question_topics`, `question_concepts`, `paper_topics`, `paper_concepts`, `topic_concepts`, `dataset_packet_topics`. No surviving table holds an FK to them (FKs were removed in migrations 010/012), so the drop is unblocked. Register in `_MIGRATIONS` as key `21`.

### 3. `schema.py` — remove eight ORM models
`Topic`, `Concept`, `QuestionTopic`, `QuestionConcept`, `PaperTopic`, `PaperConcept`, `TopicConcept`, `DatasetPacketTopic`. Required so `create_all` no longer resurrects the tables (see failure mode 2).

### 4. Straggler cutover (must precede deletion)
- **`agents/research_agent.py` (lines ~463–481):** the `record_research_question` and `extract_question_topics` tool handlers stop calling legacy `extract_question_topics`; repoint to the engine's `suggest_groupings`. Confirm the agent's tool list/schema stays consistent with the new behavior.
- **`api/routes/knowledge_library.py` `_detach_paper_links` / `_restore_paper_links`:** remove the `PaperTopic` / `PaperConcept` preservation branches. Paper↔topic/concept links now live in FK-less `grouping_links`, so the DuckDB-UPDATE workaround (migration 012 / LOG-037) no longer needs to preserve them. Verify no remaining FK-bearing child of `papers` is left unprotected by the simplification.

### 5. Remove `db/topic_store.py`
Its sole live caller is `research_agent.py` (cut over in step 4). Delete the module.

### 6. Tests
- **Delete** legacy-only suites whose behavior is already covered by the grouping engine: `test_topic_store.py`, `test_question_topic_store.py`, `test_extract_question_topics.py`, `test_topic_concepts_schema.py`, `test_phase2_topic_bundle.py`. Before deleting, confirm the equivalent assertions exist in the grouping-engine suites; port any unique coverage rather than lose it.
- **Keep** migration tests `test_question_migration_016` and `test_migration_017_groupings`; they create their own legacy fixture rows, so the 017 guard passes and they remain valid.
- **Update** `test_api_knowledge_library.py` if the detach/restore simplification changes observable behavior.
- **Add** a migration-021 test asserting the eight tables are absent after migration and that a fresh build (017 backfill skipped, no legacy data) succeeds and leaves `groupings`/`grouping_links` intact.

### 7. Gate
- `grep` proves zero non-historical references to the legacy table/model names (only migration 017's guarded backfill may name them).
- Full `uv run pytest tests/ -q` green — no new failures beyond `docs/testLog.md`.

---

## Preserved — explicitly NOT touched

- The question API contract: `topics: [...]` / `concepts: [...]` response arrays and `AddTopicLinkRequest` / `AddConceptLinkRequest`, now sourced from `groupings` / `grouping_links`.
- Migration 017's (now guarded) backfill code that names legacy tables — correct migration history.
- The surviving `research_questions.topic_id` and `study_notes.topic_id` / `concept_id` columns (deferred; see Decisions).

---

## Testing & Reproducibility

- Per-change unit/integration tests; all run under `uv run pytest tests/ -q` with the standing pass criterion.
- **Fresh-build parity:** building a DB from scratch with the legacy models gone runs 017 (backfill skipped) and 021 (drop) cleanly and yields a working groupings schema.
- **Restart safety:** after 021 applies, a subsequent startup's `create_all` must NOT recreate the legacy tables (guaranteed by model removal in step 3) — add/extend a test or manual check covering a second init pass.
- Matcher behavior reached via the repointed `research_agent` handlers uses the existing `suggest_groupings` tests (mocked `ModelClient`); no live model calls in the suite.

## Manual verification

This phase is backend/schema-only with no new user-visible workflow; the existing Groupings Phase 4 manual plan already covers the consumer behavior. No new manual test plan is required. If the `research_agent` cutover changes an agent-visible tool result, fold a check into the Phase 4 manual plan rather than creating a new one.

---

## Status doc sync

On completion: mark Unified Groupings Phase 5 complete in `docs/projectStatus.md` (Research epoch row + active focus), update the test count, and add this spec + the Phase 5 implementation plan to the reference table.
