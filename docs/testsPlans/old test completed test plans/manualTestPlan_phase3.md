# Phase 3 Manual Test Plan — Second Source + Merge Layer

**Status:** Passed
**Tester:** Eric Herrmann
**Scope:** Allen Brain Atlas connector, unified SQL views, field coverage audit script
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

Expected: `27 passed`

---

## Regression Check — Re-run Phase 2 Plan

Before testing Phase 3 additions, verify that Phase 2 behaviour is intact.

Execute all tests in `docs/testsPlans/old test completed test plans/manualTestPlan_phase2.md` (Tests 1–6). All pass criteria in that document must be satisfied before proceeding.

| # | Check | Expected |
|---|-------|----------|
| R.1 | Phase 2 Tests 1–6 complete | All pass criteria met |
| R.2 | `27 passed` from `uv run pytest tests/ -v` | No regressions |

**Sign-off:** _________________________________ Date: _____________

---

## Test 1 — Allen Brain ingest (live API)

**Goal:** Allen Brain Atlas data is fetched, filtered, and stored correctly.

```bash
# Remove any existing DB from prior runs
rm -f neurodb.db

# Run OpenNeuro ingest first (Phase 3 views require both sources)
uv run scripts/ingest.py --source openneuro --limit 50 --db neurodb.db

# Run Allen Brain ingest
uv run scripts/ingest.py --source allen_brain --limit 50 --db neurodb.db
```

Expected output for Allen ingest (values will vary):
```
Ingest complete: run_id=2, source=allen_brain, at=<ISO timestamp>
```

Note: Allen Brain API returns up to 50 records, but records with `failed=True` are
filtered out before persisting. Expect 35–50 rows stored (not necessarily 50).

| # | Step | Expected |
|---|------|----------|
| 1.1 | Allen ingest exits without error | Exit code 0, no exception printed |
| 1.2 | Two rows in `ingest_runs` | `run_id=1` for openneuro, `run_id=2` for allen_brain |
| 1.3 | `neurodb.db` file exists and is non-empty | `ls -lh neurodb.db` shows size > 0 |

Verify via SQL:
```bash
sqlite3 neurodb.db "SELECT id, source, run_at FROM ingest_runs;"
```

Expected: 2 rows, one per source.

---

## Test 2 — Allen datasets visible in DB

**Goal:** Allen records are stored with correct fields and linked to `datasets_index`.

```bash
# Row count
sqlite3 neurodb.db "SELECT COUNT(*) FROM allen_datasets;"
```

Expected: 35–50 (matches ingest output above).

```bash
# Confirm datasets_index entries for allen_brain
sqlite3 neurodb.db "SELECT COUNT(*) FROM datasets_index WHERE source = 'allen_brain';"
```

Expected: same count as above.

| # | Step | Expected |
|---|------|----------|
| 2.1 | `allen_datasets` row count is > 0 | At least 35 rows |
| 2.2 | `datasets_index` has matching `allen_brain` entries | Count equals `allen_datasets` count |
| 2.3 | All Allen rows have `modality = 'ISH'` | `SELECT DISTINCT modality FROM allen_datasets` returns only `ISH` |
| 2.4 | All Allen rows have non-null `source_id` | `SELECT COUNT(*) FROM allen_datasets WHERE source_id IS NULL` returns 0 |
| 2.5 | Spot-check one record | `SELECT source_id, title, modality, plane_of_section_id FROM allen_datasets LIMIT 1` returns a plausible row |

```bash
# Step 2.3
sqlite3 neurodb.db "SELECT DISTINCT modality FROM allen_datasets;"

# Step 2.4
sqlite3 neurodb.db "SELECT COUNT(*) FROM allen_datasets WHERE source_id IS NULL;"

# Step 2.5
sqlite3 neurodb.db "SELECT source_id, title, modality, plane_of_section_id FROM allen_datasets LIMIT 1;"
```

---

## Test 3 — Unified views (v_all_datasets, v_dataset_summary)

**Goal:** Views return correct cross-source results with proper NULL handling.

```bash
# Both sources present in v_all_datasets
sqlite3 neurodb.db "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source;"
```

Expected: two rows — one for `openneuro`, one for `allen_brain`.

| # | Step | Expected |
|---|------|----------|
| 3.1 | `v_all_datasets` contains both sources | `openneuro` and `allen_brain` rows present |
| 3.2 | Allen rows have NULL doi | `SELECT COUNT(*) FROM v_all_datasets WHERE source='allen_brain' AND doi IS NOT NULL` returns 0 |
| 3.3 | Allen rows have NULL n_subjects | `SELECT COUNT(*) FROM v_all_datasets WHERE source='allen_brain' AND n_subjects IS NOT NULL` returns 0 |
| 3.4 | `v_dataset_summary` groups correctly | Shows `ISH` row for allen_brain and multiple modality rows for openneuro |
| 3.5 | OpenNeuro subjects total is positive | `total_subjects` for openneuro rows is > 0 |
| 3.6 | Allen total_subjects is NULL or 0 | Mouse specimens — no human subject count expected |

```bash
# Step 3.2
sqlite3 neurodb.db "SELECT COUNT(*) FROM v_all_datasets WHERE source='allen_brain' AND doi IS NOT NULL;"

# Step 3.3
sqlite3 neurodb.db "SELECT COUNT(*) FROM v_all_datasets WHERE source='allen_brain' AND n_subjects IS NOT NULL;"

# Step 3.4 and 3.5
sqlite3 neurodb.db "SELECT source, modality, n_datasets, total_subjects FROM v_dataset_summary ORDER BY source, modality;"
```

---

## Test 4 — v_canonical_subjects stub

**Goal:** The view exists, runs without error, and correctly returns 0 rows (cross_refs is empty — no DOI overlap found at Phase 3 review).

```bash
sqlite3 neurodb.db "SELECT COUNT(*) FROM v_canonical_subjects;"
```

Expected: `0`

| # | Step | Expected |
|---|------|----------|
| 4.1 | View exists and executes | No `no such table/view` error |
| 4.2 | Returns 0 rows | `cross_refs` is empty; no subjects qualify |

```bash
# Confirm cross_refs is empty (expected per Phase 3 review)
sqlite3 neurodb.db "SELECT COUNT(*) FROM cross_refs;"
```

Expected: `0`

---

## Test 5 — Cross-source queries via UI (SQL Query page)

Ensure the Streamlit server is running:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.db
```

Open `http://localhost:8501` in a browser and navigate to **SQL Query**.

| # | Step | Expected |
|---|------|----------|
| 5.1 | Default query is pre-filled | Text area shows `SELECT * FROM v_dataset_summary ORDER BY n_datasets DESC;` |
| 5.2 | Click **Run Query** with default | Table shows rows grouped by source and modality, with `n_datasets` and `total_subjects` columns |
| 5.3 | Both sources appear in default result | Rows for both `openneuro` and `allen_brain` visible |
| 5.4 | Run `SELECT * FROM v_all_datasets LIMIT 10;` | Returns 10 rows mixing both sources |
| 5.5 | Allen rows show NULL for doi and n_subjects | Confirmed in the result table |
| 5.6 | Run `SELECT * FROM v_canonical_subjects;` | Returns 0 rows, no error |

---

## Test 6 — Field coverage audit script

**Goal:** Audit script runs against the populated DB and prints field coverage consistent with the Phase 3 review findings.

```bash
uv run scripts/field_coverage_audit.py --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 6.1 | Script exits without error | Exit code 0 |
| 6.2 | Field Coverage table is printed | Headers: `source total has_doi has_modality has_n_subjects has_description` |
| 6.3 | Allen row shows 0 doi, 0 n_subjects, 0 description | Matches documented gaps in `docs/reviews/phase3-field-coverage.md` |
| 6.4 | OpenNeuro row shows partial doi and description coverage | `has_doi` and `has_description` are > 0 but < total |
| 6.5 | Dataset Summary section is printed | Shows ISH for allen_brain, multiple modalities for openneuro |
| 6.6 | DOI Overlap section is printed | Reports no overlap found (empty or explicit message) |

Compare output against `docs/reviews/phase3-field-coverage.md` for reference values.

---

## Test 7 — Idempotent Allen re-ingest

**Goal:** Running Allen ingest a second time does not duplicate records.

```bash
# Record current Allen row count
sqlite3 neurodb.db "SELECT COUNT(*) FROM allen_datasets;"
```

Note the count.

```bash
# Re-run Allen ingest with same limit
uv run scripts/ingest.py --source allen_brain --limit 50 --db neurodb.db
```

Expected output: `run_id=3` (new run record, same source).

```bash
# Confirm Allen row count is unchanged
sqlite3 neurodb.db "SELECT COUNT(*) FROM allen_datasets;"
```

Expected: same count as before re-ingest.

```bash
# Confirm a third ingest_run row was added
sqlite3 neurodb.db "SELECT id, source FROM ingest_runs ORDER BY id;"
```

Expected: 3 rows — openneuro (1), allen_brain (2), allen_brain (3).

| # | Step | Expected |
|---|------|----------|
| 7.1 | Re-ingest exits without error | Exit code 0, `run_id=3` printed |
| 7.2 | Allen row count unchanged | Count matches pre-re-ingest count |
| 7.3 | New ingest_run row added | 3 rows total in `ingest_runs` |

---

## Pass Criteria

All of the following must be true before signing off:

- [x] Regression check: Phase 2 Tests 1–6 all pass
- [x] Allen Brain ingest completes without error, stores 35–50 rows
- [x] Allen records have correct fields (`modality='ISH'`, non-null `source_id`)
- [x] `v_all_datasets` returns rows for both sources
- [x] NULL handling is correct: Allen rows have NULL doi and n_subjects
- [x] `v_dataset_summary` groups correctly by source and modality
- [x] `v_canonical_subjects` exists, runs, and returns 0 rows
- [x] SQL Query page default query shows `v_dataset_summary` output for both sources
- [x] Field coverage audit script runs and output matches expected gaps
- [x] Allen re-ingest is idempotent — no duplicate rows

**Sign-off:** Eric Herrmann  Date: 2026-04-13
