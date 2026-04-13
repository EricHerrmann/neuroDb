# Phase 4 Manual Test Plan — Query & Analysis Layer

**Status:** Pending
**Tester:** Eric Herrmann
**Scope:** Query CLI (`scripts/query_cli.py`) — keyword search, modality filter, source filter, raw SQL mode
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

Expected: `29 passed`

---

## Regression Check — Re-run Phase 3 Plan

**Assumption:** You have already run `docs/manualTestPlan_phase3.md` (Tests 1–7) and all pass criteria in that document were met. You do not need to re-run Phase 3 from scratch — only confirm the regression items below.

Run the two ingest commands to populate a fresh DB (required for all Phase 4 tests):

```bash
rm -f neurodb.db
uv run scripts/ingest.py --source openneuro --limit 50 --db neurodb.db
uv run scripts/ingest.py --source allen_brain --limit 50 --db neurodb.db
```

Then verify Phase 3 behavior is still intact:

| # | Check | Expected |
|---|-------|----------|
| R.1 | `uv run pytest tests/ -v` | `29 passed`, no failures |
| R.2 | Both sources in `v_all_datasets` | `sqlite3 neurodb.db "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source;"` returns two rows |
| R.3 | Field coverage audit still runs | `uv run scripts/field_coverage_audit.py --db neurodb.db` exits without error |

**Sign-off:** _________________________________ Date: _____________

---

## Test 1 — Keyword search

**Goal:** `--search` filters datasets by title and description across all sources.

```bash
uv run scripts/query_cli.py --search "memory" --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 1.1 | Command exits without error | Exit code 0, no exception printed |
| 1.2 | Result set is non-empty | At least 1 result printed |
| 1.3 | Each result line shows source, source_id, title, modality, n_subjects | Format: `[source] id — title (modality, n=N)` |
| 1.4 | Final line shows result count | e.g. `4 result(s)` |
| 1.5 | All results contain "memory" in title or description (spot-check) | Scan result titles; none should be clearly unrelated |

Try a keyword that should return no results:

```bash
uv run scripts/query_cli.py --search "xyzzy_not_a_dataset" --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 1.6 | Returns `0 result(s)` | No results printed above the count line |

---

## Test 2 — Modality filter

**Goal:** `--modality` filters datasets to a single modality, case-insensitive.

```bash
uv run scripts/query_cli.py --modality eeg --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 2.1 | Command exits without error | Exit code 0 |
| 2.2 | All printed results have modality `eeg` | No MRI or ISH rows appear |
| 2.3 | Result count matches `sqlite3 neurodb.db "SELECT COUNT(*) FROM v_all_datasets WHERE LOWER(modality)='eeg';"` | Counts are equal |

Try with a different casing to confirm case-insensitivity:

```bash
uv run scripts/query_cli.py --modality EEG --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 2.4 | Result count matches Test 2.3 | Case does not affect the filter |

---

## Test 3 — Source filter

**Goal:** `--source` limits results to a single data source.

```bash
uv run scripts/query_cli.py --source openneuro --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | Command exits without error | Exit code 0 |
| 3.2 | All result lines start with `[openneuro]` | No `[allen_brain]` rows appear |
| 3.3 | Result count is > 0 | At least 1 result |

```bash
uv run scripts/query_cli.py --source allen_brain --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 3.4 | All result lines start with `[allen_brain]` | No `[openneuro]` rows appear |
| 3.5 | Result count matches `sqlite3 neurodb.db "SELECT COUNT(*) FROM v_all_datasets WHERE source='allen_brain';"` | Counts are equal |

---

## Test 4 — Combined filters

**Goal:** Multiple flags compose correctly (AND logic).

```bash
uv run scripts/query_cli.py --modality mri --source openneuro --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 4.1 | Command exits without error | Exit code 0 |
| 4.2 | All results are `[openneuro]` | No allen_brain rows |
| 4.3 | All results have modality `mri` | No EEG or other modalities |

```bash
uv run scripts/query_cli.py --search "brain" --modality mri --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 4.4 | Results contain "brain" in title (spot-check) | Keyword filter applied alongside modality |
| 4.5 | All results have modality `mri` | Modality filter not dropped when combined |

---

## Test 5 — Raw SQL mode

**Goal:** `--sql` executes arbitrary SQL and prints tab-separated output.

```bash
uv run scripts/query_cli.py --sql "SELECT * FROM v_dataset_summary" --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 5.1 | Command exits without error | Exit code 0 |
| 5.2 | Output has at least 2 rows | One row per source/modality grouping |
| 5.3 | Both `openneuro` and `allen_brain` appear in output | Cross-source summary visible |
| 5.4 | Output is tab-separated | Each field separated by `\t` |

```bash
uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) as n FROM v_all_datasets GROUP BY source ORDER BY n DESC" --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 5.5 | Two rows printed | One per source |
| 5.6 | Counts are positive integers | No NULL or zero counts |

Try an intentionally invalid SQL query:

```bash
uv run scripts/query_cli.py --sql "SELECT * FROM no_such_table" --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 5.7 | An error message is printed | SQLAlchemy or sqlite3 error message visible; CLI does not hang |

---

## Test 6 — Hypothesis query: modality distribution across sources

**Goal:** Answer "which modalities are most represented across sources?" — the Phase 4 baseline analysis.

```bash
uv run scripts/query_cli.py \
  --sql "SELECT modality, source, COUNT(*) as n_datasets, SUM(n_subjects) as total_subjects \
         FROM v_all_datasets \
         GROUP BY modality, source \
         ORDER BY n_datasets DESC" \
  --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 6.1 | Command exits without error | Exit code 0 |
| 6.2 | Output has multiple rows | At least 4 rows (openneuro has multiple modalities) |
| 6.3 | `mri` or `eeg` rows appear near the top | Most represented OpenNeuro modalities |
| 6.4 | `ISH` row appears for `allen_brain` | Allen data is included in the distribution |
| 6.5 | Allen `total_subjects` is NULL or 0 | Mouse specimen data — no human subject count |

Record the top modality here for future reference:

> **Top modality (by dataset count):** _________________________

---

## Test 7 — Idempotency check

**Goal:** Re-running ingest after CLI usage does not corrupt query results.

```bash
# Re-run OpenNeuro ingest
uv run scripts/ingest.py --source openneuro --limit 50 --db neurodb.db

# Re-run the keyword search from Test 1
uv run scripts/query_cli.py --search "memory" --db neurodb.db
```

| # | Step | Expected |
|---|------|----------|
| 7.1 | Ingest exits without error | Exit code 0 |
| 7.2 | Query result count matches Test 1.4 | No duplicate results introduced |
| 7.3 | No new `ingest_runs` rows cause duplicates | `sqlite3 neurodb.db "SELECT COUNT(*) FROM v_all_datasets;"` is unchanged |

---

## Pass Criteria

All of the following must be true before signing off:

- [ ] Regression check: Phase 3 regression items R.1–R.3 pass
- [ ] Keyword search returns results and the zero-match case returns `0 result(s)`
- [ ] Modality filter returns only the requested modality, case-insensitive
- [ ] Source filter returns only the requested source
- [ ] Combined filters compose correctly (AND logic)
- [ ] Raw SQL mode executes and prints tab-separated output
- [ ] `v_dataset_summary` SQL query shows both sources
- [ ] Hypothesis query (modality distribution) runs and shows meaningful output
- [ ] Re-ingest after CLI usage does not duplicate query results

**Sign-off:** _________________________________ Date: _____________
