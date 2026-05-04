# Phase 5 Manual Test Plan Review

Date: 2026-04-13
Reviewer: Codex
Target: `docs/manualTestPlan_phase5.md`

## Verdict

The Phase 5 manual plan has solid happy-path coverage for the new DuckDB CLI workflow: fresh ingest, query CLI filters, SQL mode, migration smoke test, and re-ingest idempotency are all covered.

It is not sufficient as a full Phase 5 sign-off for "replace the SQLite backend with DuckDB" as defined in `docs/ClaudeDbEpochPlan.md:2045-2047`. The current plan leaves backend-sensitive surfaces untested, including at least one already-shipped UI path and one auxiliary script that still assume SQLite.

## Findings

### 1. High — No manual coverage for the Streamlit UI on DuckDB

`docs/manualTestPlan_phase5.md:5` limits scope to ingest, query CLI, SQL mode, cross-source views, and migration. The plan never exercises the Streamlit app, even though Phase 3 explicitly treated it as a shipped surface in manual testing (`docs/testsPlans/manualTestPlan_phase3.md:178-205`).

That omission matters because the UI entrypoint still defaults to `neurodb.db` and hardcodes a SQLite engine:

- `src/neurodb/ui/app.py:14-20`
- default `db_path = "neurodb.db"`
- `engine = get_engine(f"sqlite:///{db_path}")`

If the CLI migration passed but the UI still pointed at SQLite, the current Phase 5 plan would miss it.

Recommended addition:

- Start Streamlit against a populated DuckDB file.
- Verify Dataset Browser loads.
- Verify SQL Query page can run `SELECT * FROM v_dataset_summary`.
- Confirm the UI caption/path reflects `neurodb.duckdb`.

### 2. High — No DuckDB regression coverage for `scripts/field_coverage_audit.py`

Phase 4 regression explicitly required the field coverage audit to keep working (`docs/testsPlans/manualTestPlan_phase4.md:43-47`). Phase 5 regression narrows that to only `scripts/query_cli.py` and default DB strings (`docs/manualTestPlan_phase5.md:33-37`).

That reduction leaves a real gap because `scripts/field_coverage_audit.py` still defaults to SQLite and constructs a SQLite URL:

- `scripts/field_coverage_audit.py:35-42`
- `parser.add_argument("--db", default="neurodb.db")`
- `engine = get_engine(f"sqlite:///{args.db}")`

Assuming prior-phase regression passed on SQLite does not validate this script after the backend swap. A Phase 5 manual sign-off should include at least one DuckDB smoke run of this script.

### 3. Medium — Migration coverage only proves single-source copy, not the full multi-source path

The migration script copies both source tables (`scripts/migrate_to_duckdb.py:16-25`), but the manual test seeds only OpenNeuro before migration (`docs/manualTestPlan_phase5.md:143-154`). The expected outcome also treats Allen as an empty-table skip case (`docs/manualTestPlan_phase5.md:167-169`).

That means the manual plan does not actually prove:

- `allen_datasets` rows copy correctly from SQLite to DuckDB
- `datasets_index` links remain valid for both sources after migration
- `v_all_datasets` still exposes both sources after migration, not just after fresh DuckDB ingest

Recommended addition:

- Seed the SQLite source DB with both `openneuro` and `allen_brain`.
- After migration, verify `SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source`.
- Verify at least one Allen-backed row is queryable in the migrated DuckDB file.

### 4. Medium — No negative-path SQL test on DuckDB

Phase 4 covered invalid SQL handling (`docs/testsPlans/manualTestPlan_phase4.md:181-189`). Phase 5 keeps the SQL happy path (`docs/manualTestPlan_phase5.md:113-135`) but removes the error-path check, even though the backend and dialect changed.

That is the wrong place to reduce coverage. `docs/ClaudeDbEpochPlan.md:2051-2053` already calls out `duckdb-engine` maturity as a trade-off, so manual validation should include at least one intentionally bad query to confirm the CLI still fails visibly and does not hang.

Recommended addition:

- Run `uv run scripts/query_cli.py --sql "SELECT * FROM no_such_table"` against DuckDB.
- Expect a surfaced SQLAlchemy/DuckDB error and clean process exit.

### 5. Low — The regression prerequisite points to a stale Phase 4 document path

`docs/manualTestPlan_phase5.md:31` tells the tester to rely on `docs/manualTestPlan_phase4.md`, but the current tracked Phase 4 plan is `docs/testsPlans/manualTestPlan_phase4.md:1`.

This is a documentation/reproducibility issue rather than a runtime defect, but it makes execution ambiguous and should be corrected before sign-off.

## Coverage That Is Good

The current Phase 5 plan does cover these areas well:

- Fresh DuckDB ingest for both sources (`docs/manualTestPlan_phase5.md:43-69`)
- Query CLI keyword, modality, source, and combined filters (`docs/manualTestPlan_phase5.md:73-109`)
- SQL summary and cross-source aggregation checks (`docs/manualTestPlan_phase5.md:113-135`)
- Migration script happy path plus rerun idempotency (`docs/manualTestPlan_phase5.md:139-197`)
- Re-ingest idempotency on DuckDB (`docs/manualTestPlan_phase5.md:201-225`)

## Recommended Minimum Additions Before Approval

1. Add one Streamlit smoke test against `neurodb.duckdb`.
2. Add one `field_coverage_audit.py` smoke test against DuckDB.
3. Expand migration coverage to include both `openneuro` and `allen_brain` rows in the SQLite source DB.
4. Restore the invalid SQL/manual error-path check on DuckDB.
5. Fix the Phase 4 plan reference path.

## Bottom Line

As written, the plan is good coverage for the Phase 5 CLI happy path, but not for the full migrated product surface. I would treat it as partial coverage and add the five items above before using it as the approval gate for Phase 5.
