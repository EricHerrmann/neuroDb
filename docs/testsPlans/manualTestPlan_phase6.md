# Phase 6 Manual Test Plan — NeuroVault + DANDI Connectors

**Status:** Pending
**Tester:** Eric Herrmann
**Scope:** NeuroVault ingest, DANDI ingest, DANDI NWB enrichment, unified view with 4 sources
**Date:** <!-- fill in on execution -->

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

Expected: all automated tests pass.

---

## Regression Check — Re-run Phase 5 Plan

Before testing Phase 6 additions, verify that Phase 5 behaviour is intact.

Execute all tests in `docs/testsPlans/manualTestPlan_phase5.md` (Tests 1–6). All pass criteria in that document must be satisfied before proceeding.

| # | Check | Expected |
|---|-------|----------|
| R.1 | Phase 5 Tests 1–6 complete | All pass criteria met |
| R.2 | Automated tests all pass | No regressions |

**Sign-off:** _________________________________ Date: _____________

---

## Test 1 — NeuroVault ingest

**Goal:** NeuroVault data is fetched, filtered, and stored correctly alongside Phase 5 sources.

```bash
# Ensure Phase 5 sources are ingested first (if not already present)
uv run scripts/ingest.py --source openneuro --limit 25
uv run scripts/ingest.py --source allen_brain --limit 25

# Run NeuroVault ingest
uv run scripts/ingest.py --source neurovault --limit 50
```

Expected output for NeuroVault ingest (values will vary):
```
Ingest complete: run_id=N, source=neurovault, at=<ISO timestamp>
```

| # | Step | Expected |
|---|------|----------|
| 1.1 | NeuroVault ingest exits without error | Exit code 0, no exception printed |
| 1.2 | Records visible in unified view | See query below |
| 1.3 | Row count is > 0 | At least 1 record ingested |

Verify via SQL:
```bash
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source"
```

Expected: `neurovault` row appears with count > 0.

| # | Step | Expected |
|---|------|----------|
| 1.4 | `neurovault` entries exist | `neurovault` row in GROUP BY result |

---

## Test 2 — DANDI ingest (stage 1)

**Goal:** DANDI metadata is fetched and stored; NWB fields remain NULL before enrichment.

```bash
# Run DANDI ingest
uv run scripts/ingest.py --source dandi --limit 50
```

Expected output for DANDI ingest (values will vary):
```
Ingest complete: run_id=N, source=dandi, at=<ISO timestamp>
```

| # | Step | Expected |
|---|------|----------|
| 2.1 | DANDI ingest exits without error | Exit code 0, no exception printed |
| 2.2 | DANDI records visible | `dandi` row in GROUP BY query with count > 0 |
| 2.3 | NWB fields are null pre-enrichment | See query below |

Verify that NWB fields are NULL before enrichment:
```bash
uv run scripts/query_cli.py --sql "SELECT source_id, electrode_count, brain_regions FROM dandi_datasets LIMIT 5"
```

| # | Step | Expected |
|---|------|----------|
| 2.4 | `electrode_count` is NULL | Field not yet populated |
| 2.5 | `brain_regions` is NULL | Field not yet populated |
| 2.6 | `source_id` is non-null | DANDI ID is present |

---

## Test 3 — DANDI NWB enrichment (stage 2)

**Goal:** NWB files are parsed; electrode and brain region data populate DANDI records.

```bash
# Run enrichment on a small subset
uv run scripts/enrich.py --source dandi --limit 5
```

Expected output:
```
Enrichment complete: N records enriched.
```

Progress output may include per-record status like:
```
  000003: enriched (N electrodes)
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | Enrichment command exits without error | Exit code 0, no exception printed |
| 3.2 | Records marked as enriched | Output shows count > 0 or success messages |

Verify that NWB fields are populated after enrichment:
```bash
uv run scripts/query_cli.py --sql "SELECT source_id, electrode_count, brain_regions, enriched_at FROM dandi_datasets WHERE enriched_at IS NOT NULL LIMIT 5"
```

| # | Step | Expected |
|---|------|----------|
| 3.3 | `enriched_at` is set (not NULL) | ISO timestamp visible |
| 3.4 | `electrode_count` populated | Integer >= 0 or NULL if dataset has no electrodes |
| 3.5 | `brain_regions` populated or NULL | JSON array string or NULL (not all datasets have electrodes) |

---

## Test 4 — Unified view with 4 sources

**Goal:** All four sources (openneuro, allen_brain, neurovault, dandi) are visible in the unified view.

```bash
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source ORDER BY source"
```

| # | Step | Expected |
|---|------|----------|
| 4.1 | 4 rows returned | `allen_brain`, `dandi`, `neurovault`, `openneuro` all present |
| 4.2 | All counts > 0 | Each source ingested at least some records |
| 4.3 | Allen count unchanged from Phase 5 | No data loss from prior phase |
| 4.4 | OpenNeuro count unchanged from Phase 5 | No data loss from prior phase |

Sample query to verify specific source counts:
```bash
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) as n FROM v_all_datasets WHERE source IN ('allen_brain', 'openneuro') GROUP BY source"
```

| # | Step | Expected |
|---|------|----------|
| 4.5 | Phase 5 sources unaffected | Counts match prior test runs |

---

## Test 5 — Cross-source queries via SQL CLI

**Goal:** Complex queries across all four sources execute correctly.

```bash
# Query mixing all sources
uv run scripts/query_cli.py --sql "SELECT source, modality, COUNT(*) FROM v_all_datasets WHERE modality IS NOT NULL GROUP BY source, modality ORDER BY source, modality"
```

| # | Step | Expected |
|---|------|----------|
| 5.1 | Query executes without error | Results returned |
| 5.2 | Multiple modalities represented | ISH (Allen), fMRI/dMRI/etc (OpenNeuro), map/roi (NeuroVault), behavior/icephys/etc (DANDI) |

```bash
# Query on enriched DANDI records
uv run scripts/query_cli.py --sql "SELECT COUNT(*) as enriched FROM dandi_datasets WHERE enriched_at IS NOT NULL"
```

| # | Step | Expected |
|---|------|----------|
| 5.3 | Enriched record count > 0 | At least some DANDI records successfully enriched |

---

## Test 6 — Idempotent re-ingest

**Goal:** Running ingest again does not duplicate records.

Record current counts:
```bash
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source ORDER BY source"
```

Note the counts for each source.

```bash
# Re-run both new sources with same limit
uv run scripts/ingest.py --source neurovault --limit 50
uv run scripts/ingest.py --source dandi --limit 50
```

Expected: both complete without error.

```bash
# Confirm counts are unchanged
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source ORDER BY source"
```

| # | Step | Expected |
|---|------|----------|
| 6.1 | Both re-ingests exit without error | Exit code 0 for each |
| 6.2 | Row counts unchanged | Same counts as before re-ingest |
| 6.3 | No duplicate records created | Each source count remains stable |

---

## Test 7 — Idempotent re-enrichment

**Goal:** Running enrichment again skips already-enriched records.

```bash
# Re-run enrichment on same limit
uv run scripts/enrich.py --source dandi --limit 5
```

Expected output:
```
Enrichment complete: 0 records enriched.
```

(If some records were not enriched on first pass due to errors or missing data, 0 is still valid—second pass either enriches missed records or skips already-enriched ones.)

| # | Step | Expected |
|---|------|----------|
| 7.1 | Command exits without error | Exit code 0 |
| 7.2 | Enrichment is idempotent | Output shows 0 or very few records enriched (already done on first pass) |

---

## Test 8 — UI: Cross-source browsing (optional)

**Goal:** Streamlit UI displays data from all four sources correctly.

Start the Streamlit server:
```bash
uv run streamlit run src/neurodb/ui/app.py
```

Open `http://localhost:8501` in a browser.

| # | Step | Expected |
|---|------|----------|
| 8.1 | SQL Query page loads | No errors in browser console |
| 8.2 | Default query displays | Shows `v_dataset_summary` or equivalent |
| 8.3 | Run `SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source` | All 4 sources appear with counts > 0 |
| 8.4 | View is responsive | No timeouts or 502 errors |

---

## Pass Criteria

All of the following must be true before signing off:

- [ ] Regression check: Phase 5 Tests 1–6 all pass
- [ ] NeuroVault ingest completes without error, stores records
- [ ] DANDI ingest completes without error; NWB fields are NULL before enrichment
- [ ] Enrichment populates NWB fields on DANDI records; `enriched_at` is a timestamp
- [ ] All 4 sources (allen_brain, dandi, neurovault, openneuro) appear in `v_all_datasets` with count > 0
- [ ] Phase 5 sources (allen_brain, openneuro) are unaffected; counts unchanged
- [ ] Cross-source queries execute correctly and return data from all sources
- [ ] Re-ingest of both new sources is idempotent (no duplicate rows)
- [ ] Re-enrichment is idempotent (0 or minimal records enriched on second pass)

**Sign-off:** _________________________________ Date: _____________
