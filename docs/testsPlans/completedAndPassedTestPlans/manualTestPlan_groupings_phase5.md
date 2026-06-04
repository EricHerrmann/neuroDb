# Manual Test Plan — Groupings Phase 5 (Legacy Table Retirement)

**Status:** Complete — T1-T4 passed and signed off 2026-06-04
**Date created:** 2026-06-04
**Design spec:** `docs/superpowers/specs/2026-06-04-groupings-phase5-legacy-drop-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-06-04-groupings-phase5-legacy-drop.md`

This is the live-system completion gate for the unified-groupings effort. Phase 5 is backend/schema-only: it drops the legacy `topics`/`concepts` tables and their six join tables via migration 021 and removes their ORM models. Automated tests already cover the migration logic on in-memory SQLite and on a fresh DuckDB. This plan covers what automation cannot:

1. the real DuckDB **upgrade path** — applying the drop to a populated database that still has the legacy tables;
2. **restart safety** in the live server process — confirming `create_all` does not resurrect the dropped tables on a second startup;
3. an **end-to-end smoke** of the surfaces formerly backed by the legacy tables — including the research-question capture/categorize workflow now delivered through the groupings engine — running against the post-drop database.

> The research-question Phase 1 workflows (create, suggest, confirm/dismiss, filter, collapse, delete) were delivered through groupings Phases 3–4 and were manually verified pre-drop in the signed-off `manualTestPlan_groupings_phase4.md` (T5–T7) and `manualTestPlan_groupings_phase3b.md`. T3 below re-verifies them on the post-drop live system; the standalone `manualTestPlan_research_question_phase1.md` is superseded by that coverage.

---

## Prerequisites

- [x] Run the automated backend suite: `uv run pytest tests/ -q`. Pass criterion: no new failures beyond those already tracked in `docs/testLog.md`.
- [x] Prepare a pre-drop DuckDB (legacy tables present, schema version 20): `uv run python tests/manual/phase5_prepare_pre_drop_db.py --target-db /tmp/neurodb_phase5_pre_drop.duckdb --force`. Pass criterion: prints `PASS: pre-drop DB ready ... schema version 20.` *(Alternatively, use a copy of an actual pre-Phase-5 `neurodb.duckdb` that still contains the legacy tables.)*
- [x] Start the backend against that DB so migrations apply on startup: `NEURODB_DB_PATH=/tmp/neurodb_phase5_pre_drop.duckdb uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`. Pass criterion: the server starts with no migration error in the log.
- [x] Start the frontend: `cd frontend && npm run dev` (Vite proxies `/api` to port 8001).

## T1 — Migration 021 drops the legacy tables on a populated DuckDB (upgrade path)
- [x] With the backend started against the prepared pre-drop DB (Prerequisite 3), stop the backend so the DuckDB file lock is released (DuckDB is single-writer).
- [x] Run: `uv run python tests/manual/phase5_verify_legacy_dropped.py --db /tmp/neurodb_phase5_pre_drop.duckdb`.
- [x] Pass: prints `PASS: legacy taxonomy tables dropped; groupings/grouping_links present; schema version 21.` — the eight legacy tables are gone, `groupings`/`grouping_links` remain, and the migration applied without manual intervention.

## T2 — Restart safety: `create_all` does not resurrect dropped tables
- [x] Restart the backend against the same DB a second time (same `NEURODB_DB_PATH`), let it finish startup, then stop it.
- [x] Re-run: `uv run python tests/manual/phase5_verify_legacy_dropped.py --db /tmp/neurodb_phase5_pre_drop.duckdb`.
- [x] Pass: still prints `PASS` — the legacy tables do not reappear after a second startup. (Confirms the ORM-model removal prevents `create_all` from recreating them before the already-applied migration 021 could re-fire.)

## T3 — Research-question workflow end-to-end on the post-drop system
- [x] Restart the backend against the post-drop DB and open the Research panel.
- [x] Create a new research question and wait for the background matcher.
- [x] Pass: pending topic/concept suggestion chips (including any "new"/proposed chips) appear without a manual page reload; confirming a chip turns it into a confirmed badge; filtering by that topic returns the question; deleting the question removes it and clears its pending/proposed-only links — all with no errors against the legacy-table-free DB.

## T4 — Tutor / Knowledge Library / Study Log smoke on the post-drop system
- [x] Tutor: ask for a cited paper recommendation on a topic; confirm it queues to Knowledge Library and the related topic grouping appears in the Research topic filter/hierarchy.
- [x] Knowledge Library: approve a pending paper that has topic grouping links; confirm the grouping link survives approval (DuckDB-backed UPDATE path).
- [x] Study Log: confirm topic/concept-anchored notes still list and resolve their anchor labels.
- [x] Pass: all three surfaces operate normally; the backend log shows no `no such table` / 500 errors referencing the dropped legacy tables.

## Cleanup
- [x] Remove the disposable DB and its Chroma dir: `rm -rf /tmp/neurodb_phase5_pre_drop.duckdb /tmp/neurodb_phase5_pre_drop_chroma`.

---

**Sign-off:** Passed 2026-06-04 — T1-T4 complete. T3 exposed the research-question suggestion refresh gap; fixed by delayed detail refetches after create and covered by `ResearchPanel.test.tsx`. T4 exposed missing Knowledge Library grouping-link indicators; fixed by returning/rendering `grouping_links` on pending papers and covered by `test_api_knowledge_library.py` plus `KnowledgeLibraryPanel.test.tsx`.
