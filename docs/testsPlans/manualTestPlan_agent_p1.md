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

## Test 1 — CLI: tag command ✅ PASSED

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

| # | Step | Expected | Result |
|---|------|----------|--------|
| 1.1 | Command exits without error | `Tagged dandi:<id> → 'hippocampus spatial navigation'` | ✅ |
| 1.2 | Tag visible in DB | See query below | ✅ |

```bash
uv run scripts/query_cli.py --sql "SELECT concept_tag, section_ref, note_text FROM study_notes"
```

| # | Step | Expected | Result |
|---|------|----------|--------|
| 1.3 | Row appears in study_notes | concept_tag = `hippocampus spatial navigation` | ✅ |
| 1.4 | section_ref populated | `Augustine Ch24 p.580` | ✅ |
| 1.5 | note_text populated | `electrophysiology confirms place cells` | ✅ |

---

## Test 2 — CLI: tag unknown dataset ✅ PASSED

```bash
uv run scripts/study.py tag --source dandi --id NOT-A-REAL-ID --concept "test"
```

| # | Step | Expected | Result |
|---|------|----------|--------|
| 2.1 | Error message printed | `Dataset not found: dandi:NOT-A-REAL-ID — run ingest first` | ✅ |
| 2.2 | No row created | study_notes count unchanged | ✅ |

---

## Test 3 — CLI: list command ✅ PASSED

```bash
uv run scripts/study.py list
```

| # | Step | Expected | Result |
|---|------|----------|--------|
| 3.1 | Tag from Test 1 appears | source, source_id, concept_tag, note visible | ✅ |

```bash
uv run scripts/study.py list --concept "hippo"
```

| # | Step | Expected | Result |
|---|------|----------|--------|
| 3.2 | Filtered to matching tags | Only tags containing "hippo" in concept_tag shown | ✅ |

---

## Test 4 — CLI: search command ✅ PASSED

```bash
uv run scripts/study.py search "place cells"
```

| # | Step | Expected | Result |
|---|------|----------|--------|
| 4.1 | Tag from Test 1 returned | note_text "place cells" match surfaces the tag | ✅ |

```bash
uv run scripts/study.py search "somatosensory"
```

| # | Step | Expected | Result |
|---|------|----------|--------|
| 4.2 | No match | `No tags matching 'somatosensory'` | ✅ |

---

## Test 5 — UI: Study Log browse section ✅ PASSED

```bash
uv run streamlit run src/neurodb/ui/app.py
```

Open `http://localhost:8501`.

| # | Step | Expected | Result |
|---|------|----------|--------|
| 5.1 | App connects to DuckDB | Caption shows `neurodb.duckdb` | ✅ |
| 5.2 | Study Log appears in sidebar | Third nav option visible | ✅ |
| 5.3 | Navigate to Study Log | Page loads without error | ✅ |
| 5.4 | Tag from Test 1 appears in table | Row visible with correct concept_tag and note | ✅ |
| 5.5 | Concept filter works | Type "hippo" → only matching tags shown | ✅ |
| 5.6 | Source filter works | Select "openneuro" → dandi tags hidden | ✅ |

---

## Test 6 — UI: Study Log tag-by-ID form

You are already on the Study Log page. Below the **Your Study Tags** browse
section (with the Filter by concept and Filter by source inputs) you will see
a tag form. This lets you tag any ingested dataset directly from the UI.

**6.1 — Confirm the form is visible**
Scroll below the Your Study Tags table. You should see four fields:
Source (dropdown), Source ID (text), Concept tag * (text), Section reference
(text), and a Note textarea. The button is labelled **Save Tag**.

**6.2 — Tag a valid dataset**
- Source: `dandi`
- Source ID: `000003` (or any DANDI ID you know is ingested)
- Concept tag: `ui-tagged concept`
- Leave Section reference and Note blank.
- Click **Save Tag**.
- Expected: green message — `Tagged dandi:000003 → 'ui-tagged concept'`
  The Your Study Tags table above should refresh and show the new row.

**6.3 — Attempt an unknown dataset ID**
- Source: `dandi`
- Source ID: `FAKE-99999`
- Concept tag: `should fail`
- Click **Save Tag**.
- Expected: red error — `Dataset not found: dandi:FAKE-99999 — run ingest first.`

**6.4 — Attempt to save with empty concept tag**
- Source: `dandi`, Source ID: `000003`, leave Concept tag blank.
- Click **Save Tag**.
- Expected: red error — `Concept tag is required.`

| # | Step | Expected |
|---|------|----------|
| 6.1 | Form visible below Your Study Tags section | Source dropdown, Source ID, Concept tag *, Section reference, Note, Save Tag button |
| 6.2 | Save Tag with valid source ID | Green: `Tagged dandi:000003 → 'ui-tagged concept'`; table refreshes |
| 6.3 | Save Tag with unknown source ID | Red: `Dataset not found: dandi:FAKE-99999 — run ingest first.` |
| 6.4 | Save Tag with empty concept tag | Red: `Concept tag is required.` |

---

## Test 7 — UI: Dataset Browser inline tag expander

This test is on the **Dataset Browser** page — a different page from Study Log.

**7.1 — Navigate and search**
- In the sidebar, click **Dataset Browser**.
- Run any search (or leave the box blank to load all results).
- Scroll below the results dataframe — you should see a collapsed triangle
  labelled **"Tag a dataset from these results"**.

**7.2 — Open the expander**
- Click **"Tag a dataset from these results"** to expand it.
- Inside you will see: a **Dataset** dropdown pre-filled with the datasets
  from your search results, a **Concept tag** field, a **Section reference**
  field, and a **Save Tag** button.

**7.3 — Save a tag**
- Select any dataset from the Dataset dropdown.
- Concept tag: `browser-tagged concept`
- Click **Save Tag**.
- Expected: green message — `Tagged <dataset> → 'browser-tagged concept'`
  The page refreshes automatically.

**7.4 — Verify in Study Log**
- Click **Study Log** in the sidebar.
- The tag you just created should appear as a new row in the Your Study Tags table.

| # | Step | Expected |
|---|------|----------|
| 7.1 | "Tag a dataset from these results" expander visible | Collapsed section below the results dataframe in Dataset Browser |
| 7.2 | Expander opens to form | Dataset dropdown pre-populated with search results; Concept tag field; Save Tag button |
| 7.3 | Save Tag for a dataset | Green: `Tagged <dataset> → 'browser-tagged concept'`; page refreshes |
| 7.4 | Navigate to Study Log | New tag row visible in Your Study Tags table |

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
