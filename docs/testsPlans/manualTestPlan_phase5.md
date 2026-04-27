# Phase 5 Manual Test Plan — DuckDB Migration

**Status:** PASSED
**Tester:** Eric Herrmann
**Scope:** DuckDB backend — ingest, query CLI, SQL mode, cross-source views, migration script
**Date:** 2026-04-13

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

```bash
# Confirm you are on master with a clean working tree
git status

# Install / sync dependencies
uv sync

# Confirm automated tests pass before beginning
uv run pytest tests/ -v
```

Expected: `35 passed` (29 prior + 6 new DuckDB integration tests)

---

## Regression Check — Re-run Phase 4 Plan

**Assumption:** You have already run `docs/manualTestPlan_phase4.md` (Tests 1–7) and all pass criteria were met. You do not need to re-run Phase 4 from scratch — only confirm the regression items below.

| # | Check | Expected |
|---|-------|----------|
| R.1 | `uv run pytest tests/ -v` | `35 passed`, no failures |
| R.2 | `uv run scripts/query_cli.py --search "memory"` exits without error | Uses DuckDB by default (`neurodb.duckdb`) |
| R.3 | Default `--db` flag in both scripts is `neurodb.duckdb` | `grep "neurodb.duckdb" scripts/ingest.py scripts/query_cli.py` returns 2 matches |

**Sign-off:** _________________________________ Date: _____________

---

## Test 1 — Fresh DuckDB ingest (both sources)

**Goal:** Ingest runs end-to-end against a new DuckDB file.

```bash
# Remove any existing DuckDB file
rm -f neurodb.duckdb

# Ingest OpenNeuro
uv run scripts/ingest.py --source openneuro --limit 50

# Ingest Allen Brain
uv run scripts/ingest.py --source allen_brain --limit 50
```

| # | Step | Expected |
|---|------|----------|
| 1.1 | OpenNeuro ingest exits without error | `Ingest complete: run_id=1, source=openneuro, at=<timestamp>` |
| 1.2 | Allen ingest exits without error | `Ingest complete: run_id=2, source=allen_brain, at=<timestamp>` |
| 1.3 | `neurodb.duckdb` file exists and is non-empty | `ls -lh neurodb.duckdb` shows size > 0 |
| 1.4 | Both sources visible in unified view | See SQL below |

```bash
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source"
```

Expected: two rows — one for `openneuro`, one for `allen_brain`.

---

## Test 2 — Query CLI keyword, modality, and source filters

**Goal:** All Phase 4 query modes work identically on DuckDB.

```bash
uv run scripts/query_cli.py --search "memory"
```

| # | Step | Expected |
|---|------|----------|
| 2.1 | Returns at least 1 result | Result lines in `[source] id — title (modality, n=N)` format |
| 2.2 | Count line is printed | e.g. `4 result(s)` |

```bash
uv run scripts/query_cli.py --modality eeg
```

| # | Step | Expected |
|---|------|----------|
| 2.3 | All results have modality `eeg` | No non-EEG rows visible |

```bash
uv run scripts/query_cli.py --source allen_brain
```

| # | Step | Expected |
|---|------|----------|
| 2.4 | All results start with `[allen_brain]` | No openneuro rows |
| 2.5 | Count > 0 | At least 35 rows |

```bash
uv run scripts/query_cli.py --modality mri --source openneuro
```

| # | Step | Expected |
|---|------|----------|
| 2.6 | Combined filter returns only openneuro MRI datasets | No EEG, no allen_brain |

---

## Test 3 — SQL mode and summary view

**Goal:** Raw SQL queries execute correctly against DuckDB.

```bash
uv run scripts/query_cli.py --sql "SELECT * FROM v_dataset_summary ORDER BY n_datasets DESC"
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | Command exits without error | Exit code 0 |
| 3.2 | Output has multiple rows | At least 4 rows (openneuro has multiple modalities) |
| 3.3 | Both `openneuro` and `allen_brain` appear | Cross-source summary visible |
| 3.4 | Output is tab-separated | Fields separated by `\t` |

```bash
uv run scripts/query_cli.py --sql "SELECT modality, source, COUNT(*) as n FROM v_all_datasets GROUP BY modality, source ORDER BY n DESC"
```

| # | Step | Expected |
|---|------|----------|
| 3.5 | ISH row appears for allen_brain | Allen data in distribution |
| 3.6 | mri or eeg near the top for openneuro | Most represented modalities |

---

## Test 4 — Migration script (SQLite → DuckDB)

**Goal:** Existing SQLite data migrates cleanly into a fresh DuckDB file.

First, create a small SQLite DB to migrate from:

```bash
uv run python -c "
from neurodb.db import get_engine, init_db, create_views
from neurodb.provenance import run_ingest
from neurodb.connectors.openneuro import OpenNeuroConnector
engine = get_engine('sqlite:///neurodb_test.db')
init_db(engine); create_views(engine)
run = run_ingest(engine, OpenNeuroConnector(), limit=5)
print(f'SQLite seeded: run_id={run.id}')
"
```

Now migrate:

```bash
rm -f neurodb_migrated.duckdb
uv run scripts/migrate_to_duckdb.py --sqlite neurodb_test.db --duckdb neurodb_migrated.duckdb
```

| # | Step | Expected |
|---|------|----------|
| 4.1 | Script exits without error | `Migration complete.` printed |
| 4.2 | `ingest_runs` row count shown | e.g. `ingest_runs: copied 1 rows` |
| 4.3 | `openneuro_datasets` rows copied | e.g. `openneuro_datasets: copied 5 rows` |
| 4.4 | Empty tables skipped cleanly | `subjects: 0 rows in source, skipping` (no error) |

Verify data is accessible in the migrated DuckDB:

```bash
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source" --db neurodb_migrated.duckdb
```

| # | Step | Expected |
|---|------|----------|
| 4.5 | openneuro row appears with count matching ingest | e.g. `openneuro  5` |
| 4.6 | No error about missing views | Views were re-created by migration script |

Re-run migration to confirm idempotency:

```bash
uv run scripts/migrate_to_duckdb.py --sqlite neurodb_test.db --duckdb neurodb_migrated.duckdb
```

| # | Step | Expected |
|---|------|----------|
| 4.7 | All tables show "already has N rows, skipping" | No duplicate rows inserted |
| 4.8 | Script exits without error | `Migration complete.` |

Clean up:

```bash
rm -f neurodb_test.db neurodb_migrated.duckdb
```

---

## Test 5 — Idempotent re-ingest on DuckDB

**Goal:** Re-running ingest against the DuckDB file does not duplicate records.

```bash
# Record current row counts
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source"
```

Note the counts.

```bash
# Re-run both ingests
uv run scripts/ingest.py --source openneuro --limit 50
uv run scripts/ingest.py --source allen_brain --limit 50

# Re-check counts
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source"
```

| # | Step | Expected |
|---|------|----------|
| 5.1 | Both re-ingests exit without error | Exit code 0 |
| 5.2 | Row counts unchanged | Counts match pre-re-ingest values |
| 5.3 | Two new `ingest_runs` rows added | `uv run scripts/query_cli.py --sql "SELECT COUNT(*) FROM ingest_runs"` returns 4 |

---

## Pass Criteria

All of the following must be true before signing off:

- [x] Regression check: Phase 4 regression items R.1–R.3 pass
- [x] Fresh DuckDB ingest completes for both sources without error
- [x] Both sources appear in `v_all_datasets` after ingest
- [x] Query CLI keyword, modality, source, and combined filters all work against DuckDB
- [x] SQL mode executes `v_dataset_summary` and cross-source group-by without error
- [x] Migration script copies SQLite data into DuckDB and creates views
- [x] Migration script is idempotent — re-run skips already-populated tables
- [x] Re-ingest is idempotent — no duplicate rows in DuckDB after second run

**Sign-off:** Eric Herrmann Date: 2026-04-13

### Notes
- Test 4 required a fix: migration script crashed on tables absent from the SQLite source (e.g. `allen_datasets`). Fixed by catching the `CatalogException` and skipping missing tables (commit `6b913e7`).
- Test 5 required a fix: re-ingest failed with a DuckDB FK constraint violation when updating `DatasetIndex.run_id`. Fixed by treating `DatasetIndex.run_id` as immutable after creation (commit `0d31164`).
