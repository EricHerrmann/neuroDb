# Phase 2 Manual Test Plan — MVP UI

**Status:** Deferred from Phase 2 approval (2026-04-11)
**Tester:** Eric Herrmann
**Scope:** Streamlit dataset browser, SQL query page, query CLI

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

```bash
# Confirm you are on master with a clean working tree
git status

# Install / sync dependencies
uv sync

# Confirm tests pass before beginning
uv run pytest tests/ -v
```

Expected: `13 passed`

---

## Test 1 — Empty DB behaviour

**Goal:** UI and CLI degrade gracefully when the database has no data.

```bash
# Remove any existing DB from a prior run
rm -f neurodb.db

# Start the Streamlit server (runs in foreground — open a second terminal for remaining steps)
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.db
```

Open `http://localhost:8501` in a browser.

| # | Step | Expected |
|---|------|----------|
| 1.1 | Navigate to **Dataset Browser** | Page loads with "Search title/description" input and "Modality" dropdown |
| 1.2 | Leave filters blank | "No datasets found. Run an ingest first…" message is shown |
| 1.3 | Navigate to **SQL Query** | Page loads with a default SQL statement pre-filled in the text area |
| 1.4 | Click **Run Query** | Returns 0 rows (no error, no crash) |

```bash
# Verify CLI also handles empty DB
uv run scripts/query_cli.py --search "plasticity" --db neurodb.db
```

Expected output:
```
No datasets found.
```

---

## Test 2 — Ingest from OpenNeuro

**Goal:** Data is fetched from the live OpenNeuro API and stored correctly.

```bash
# Run a small ingest (requires internet access)
uv run scripts/ingest.py --source openneuro --limit 5 --db neurodb.db
```

Expected output (values will vary):
```
Ingest complete: run_id=1, source=openneuro, at=<ISO timestamp>
```

Verify the DB was created:
```bash
ls -lh neurodb.db
```

Expected: file exists, size > 0.

---

## Test 3 — Dataset Browser filters

Refresh `http://localhost:8501` (or restart Streamlit if already stopped).

| # | Step | Expected |
|---|------|----------|
| 3.1 | Navigate to **Dataset Browser**, leave filters blank | Table shows up to 5 rows with columns: ID, Title, Modality, Subjects, DOI |
| 3.2 | Type `"fMRI"` in the Search box | Table filters to rows where title or description contains "fMRI" |
| 3.3 | Type a term unlikely to match (e.g. `"zzznomatch"`) | "No datasets found" message appears |
| 3.4 | Select **MRI** from the Modality dropdown | Table shows only MRI-modality rows |
| 3.5 | Select **Any** from Modality, leave search blank | Full result set returns |
| 3.6 | Confirm row count caption at bottom of table is accurate | Caption reads `"N dataset(s) found"` matching row count |

---

## Test 4 — SQL Query page

Navigate to **SQL Query** in the sidebar.

| # | Step | Expected |
|---|------|----------|
| 4.1 | Click **Run Query** with default SQL | Returns a result table grouped by modality with a count column |
| 4.2 | Replace SQL with: `SELECT * FROM openneuro_datasets LIMIT 3;` and click **Run Query** | Returns up to 3 rows with full dataset fields |
| 4.3 | Replace SQL with: `SELECT * FROM datasets_index;` and click **Run Query** | Returns rows from the shared index table |
| 4.4 | Replace SQL with: `SELECT * FROM ingest_runs;` and click **Run Query** | Returns 1 row showing the ingest run from Test 2 |
| 4.5 | Enter invalid SQL: `SELECT * FROM nonexistent_table;` and click **Run Query** | Error message displayed in the UI — no crash |

---

## Test 5 — Query CLI

```bash
# Keyword search
uv run scripts/query_cli.py --search "brain" --db neurodb.db
```

Expected: tabular output with ID, Modality, Subjects, Title columns. At least 1 result.

```bash
# Modality filter
uv run scripts/query_cli.py --modality MRI --db neurodb.db
```

Expected: only rows with Modality = MRI.

```bash
# Combined filter
uv run scripts/query_cli.py --search "brain" --modality MRI --db neurodb.db
```

Expected: intersection of both filters.

```bash
# Limit flag
uv run scripts/query_cli.py --limit 2 --db neurodb.db
```

Expected: at most 2 rows returned.

---

## Test 6 — Idempotent re-ingest

**Goal:** Running ingest twice does not duplicate records.

```bash
# Run a second ingest with the same source and limit
uv run scripts/ingest.py --source openneuro --limit 5 --db neurodb.db
```

Expected output: `run_id=2` (new run recorded, same source)

```bash
# Confirm dataset count is unchanged
uv run scripts/query_cli.py --db neurodb.db --limit 100
```

Expected: same number of results as after Test 2 (no duplicates).

Verify via SQL:
```bash
# Open the DB directly (requires sqlite3 on PATH)
sqlite3 neurodb.db "SELECT COUNT(*) FROM openneuro_datasets;"
```

Expected: count matches Test 2 count (not doubled).

---

## Pass Criteria

All of the following must be true before signing off:

- [ ] Tests 1–6 complete with no unexpected errors
- [ ] Dataset Browser renders data after ingest
- [ ] Modality and keyword filters work independently and combined
- [ ] SQL query page handles both valid and invalid SQL gracefully
- [ ] Query CLI produces formatted tabular output
- [ ] Re-ingest does not duplicate rows

**Sign-off:** <!-- Replace with: "Verified by Eric Herrmann on YYYY-MM-DD" -->
