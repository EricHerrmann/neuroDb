# Agent P1 Manual Test Plan — Study Tag Layer

**Status:** Pending
**Tester:** Eric Herrmann
**Scope:** StudyNote schema, study.py CLI, Study Log UI, Dataset Browser inline tag
**Date:** <!-- fill in on execution -->

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

```bash
git status        # confirm on main, clean working tree
uv sync           # install dependencies
uv run pytest tests/ -v   # all automated tests must pass before starting
```

Ensure at least one source is ingested:

```bash
uv run scripts/ingest.py --source dandi --limit 10
```

---

## Test 1 — CLI: tag command

```bash
# Get a DANDI source_id from the DB first
uv run scripts/query_cli.py --sql "SELECT source_id FROM dandi_datasets LIMIT 1"
```

Note the source_id returned (e.g. `000003`). Then:

```bash
uv run scripts/study.py tag \
  --source dandi \
  --id <source_id_from_above> \
  --concept "hippocampus spatial navigation" \
  --section "Augustine Ch24 p.580" \
  --note "electrophysiology confirms place cells"
```

| # | Step | Expected |
|---|------|----------|
| 1.1 | Command exits without error | `Tagged dandi:<id> → 'hippocampus spatial navigation'` |
| 1.2 | Tag visible in DB | See query below |

```bash
uv run scripts/query_cli.py --sql "SELECT concept_tag, section_ref, note_text FROM study_notes"
```

| # | Step | Expected |
|---|------|----------|
| 1.3 | Row appears in study_notes | concept_tag = `hippocampus spatial navigation` |
| 1.4 | section_ref populated | `Augustine Ch24 p.580` |
| 1.5 | note_text populated | `electrophysiology confirms place cells` |

---

## Test 2 — CLI: tag unknown dataset

```bash
uv run scripts/study.py tag --source dandi --id NOT-A-REAL-ID --concept "test"
```

| # | Step | Expected |
|---|------|----------|
| 2.1 | Error message printed | `Dataset not found: dandi:NOT-A-REAL-ID — run ingest first` |
| 2.2 | No row created | study_notes count unchanged |

---

## Test 3 — CLI: list command

```bash
uv run scripts/study.py list
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | Tag from Test 1 appears | source, source_id, concept_tag, note visible |

```bash
uv run scripts/study.py list --concept "hippo"
```

| # | Step | Expected |
|---|------|----------|
| 3.2 | Filtered to matching tags | Only tags containing "hippo" in concept_tag shown |

---

## Test 4 — CLI: search command

```bash
uv run scripts/study.py search "place cells"
```

| # | Step | Expected |
|---|------|----------|
| 4.1 | Tag from Test 1 returned | note_text "place cells" match surfaces the tag |

```bash
uv run scripts/study.py search "somatosensory"
```

| # | Step | Expected |
|---|------|----------|
| 4.2 | No match | `No tags matching 'somatosensory'` |

---

## Test 5 — UI: Study Log browse section

```bash
uv run streamlit run src/neurodb/ui/app.py
```

Open `http://localhost:8501`.

| # | Step | Expected |
|---|------|----------|
| 5.1 | App connects to DuckDB | Caption shows `neurodb.duckdb` |
| 5.2 | Study Log appears in sidebar | Third nav option visible |
| 5.3 | Navigate to Study Log | Page loads without error |
| 5.4 | Tag from Test 1 appears in table | Row visible with correct concept_tag and note |
| 5.5 | Concept filter works | Type "hippo" → only matching tags shown |
| 5.6 | Source filter works | Select "openneuro" → dandi tags hidden |

---

## Test 6 — UI: Study Log tag-by-ID form

| # | Step | Expected |
|---|------|----------|
| 6.1 | Tag-by-ID form visible below Browse section | Form with Source, Source ID, Concept tag fields |
| 6.2 | Submit with valid source ID | Green success message; Browse section updates |
| 6.3 | Submit with unknown source ID | Red error: "Dataset not found" |
| 6.4 | Submit with empty concept tag | Red error: "Concept tag is required" |

---

## Test 7 — UI: Dataset Browser inline tag expander

Navigate to **Dataset Browser**. Run a search that returns results.

| # | Step | Expected |
|---|------|----------|
| 7.1 | "Tag a dataset from these results" expander visible | Below the results dataframe |
| 7.2 | Expander opens to form | Dataset selectbox populated with results |
| 7.3 | Submit tag for a dataset | Green success message; browser refreshes |
| 7.4 | Navigate to Study Log | New tag appears |

---

## Pass Criteria

- [ ] `uv run pytest tests/ -v` — all tests pass
- [ ] CLI tag creates a row in study_notes with correct fields
- [ ] CLI tag on unknown dataset prints error and creates no row
- [ ] CLI list and search return correct results
- [ ] Streamlit app connects to `neurodb.duckdb` (not SQLite)
- [ ] Study Log browse section shows tags and filters work
- [ ] Study Log tag-by-ID form saves tags and shows errors correctly
- [ ] Dataset Browser inline expander saves tags and they appear in Study Log

**Sign-off:** _________________________________ Date: _____________
