# Manual Test Plan — UI-3: Parity Migration

**Epoch scope:** UI — all 7 write operations moved to React; Streamlit demoted to secondary.
**Phase:** UI-3
**Design source:** `docs/superpowers/specs/2026-05-11-ui3-parity-migration-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-05-11-ui3-parity-migration.md`
**Status:** Active
**Date:** 2026-05-11

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. Automated Python tests pass:

```bash
uv run pytest tests/ -q
```

2. Automated frontend tests pass:

```bash
cd frontend && npm test
```

3. Start both servers:

```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
cd frontend && npm run dev
```

Open http://localhost:5173 in a browser.

---

## Write Operation Evals

### T1 — Create Study Tag

Open Study Log panel. Select "Study Tags" in the dropdown. Click "Add Tag".

Fill in: source=openneuro, source_id=ds000001 (must be in datasets index), concept_tag=LTP, section_ref=Ch3.

Click Save.

**Pass:** New row appears in the study tag table with concept "LTP". Form closes.

### T2 — Inline Error On Missing Concept Tag

Open Study Log panel, click "Add Tag". Leave concept_tag blank. Click Save.

**Pass:** "Concept tag is required" appears inline. No API call is made.

### T3 — Dismiss Source Suggestion

Open Suggestions panel. Find a row under "Connector Requests" with status pending.

Click Dismiss.

**Pass:** Row disappears from the list; the route returns 204.

### T4 — Promote Source Suggestion To Registry

Open Suggestions panel. Find a pending source suggestion row. Click Promote.

**Pass:** Row disappears from Suggestions. Open Registry panel; the promoted entry appears as a new row under the appropriate type group.

### T5 — Remove Registry Entry

Open Registry panel. Locate any entry. Click Remove.

**Pass:** Entry disappears from the registry list after mutation completes.

### T6 — Add Registry Entry Manually

Open Registry panel. Click "Add Source". Fill in: source_type=paper, source_key=doi:10.test/manual, display_name=Test Paper, added_by=user. Click Save.

**Pass:** Form closes. New entry "Test Paper" appears in Papers & Studies group.

### T7 — Import Dataset

Open Suggestions panel. Find a pending import request. Click Import.

**Pass:** "Running..." appears inline while the task runs. On completion, "Import complete" appears in green. The Datasets panel refreshes.

If the dataset source is not configured, the task may fail. Passing behavior is a transition from Running to either Import complete or an error message, with no infinite spinner.

### T8 — Run Hypothesis Review

Open Research panel. Locate a hypothesis card. Click "Run Review".

**Pass:** "Running..." appears inline. On completion, "Review complete" appears in green. The hypotheses list re-fetches.

If no API key is configured, the task may fail. Passing behavior is a transition from Running to either Review complete or an error message, with no infinite spinner.

### T9 — Streamlit Deprecation Banner

Start the Streamlit app:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

Open http://localhost:8501.

**Pass:** Blue info banner appears at the top: "The React workbench at http://localhost:5173 is now the primary UI. This Streamlit app will be retired in UI-4."

---

## Sign-Off

| Eval | Result | Notes |
|------|--------|-------|
| T1 - Create study tag | | |
| T2 - Inline error on missing concept tag | | |
| T3 - Dismiss source suggestion | | |
| T4 - Promote source suggestion | | |
| T5 - Remove registry entry | | |
| T6 - Add registry entry | | |
| T7 - Import dataset | | |
| T8 - Run hypothesis review | | |
| T9 - Streamlit deprecation banner | | |

**Signed off:** pending
