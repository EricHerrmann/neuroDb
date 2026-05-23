# Manual Test Plan - UI-5 P1: Data Integrity Fixes

**Epoch scope:** UI - React write paths and FastAPI side effects for data integrity.
**Phase:** UI-5 P1
**Design source:** `docs/superpowers/specs/2026-05-12-ui5-p1-data-integrity-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-05-12-ui5-p1-data-integrity.md`
**Status:** Deferred; superseded by completed common plan `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_ui5_common_parity.md`
**Date:** 2026-05-13
**Last updated:** 2026-05-23

**Deferred reason:** UI-5 P1 implementation and automated verification are complete. Manual verification remained valuable for production-like browser, FastAPI, DuckDB, and ChromaDB wiring, and UI-5 completed through one consolidated P1/P2/P3 manual plan.

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

**Server rule for DB checks:** FastAPI holds the DuckDB write lock while it is
running. React/Vite does not. For any CLI check against `neurodb.duckdb`, stop
only the FastAPI backend first, leave React running, run the CLI command, then
restart FastAPI before returning to browser-based UI steps.

**Automation boundary:** Automated tests cover the route logic, warning payloads,
component rendering, and API persistence rules. This manual plan verifies the
production-like workflow across browser actions, FastAPI, DuckDB, ChromaDB,
React refresh behavior, and operator start/stop steps. Fault-injection warning
paths are optional manual checks because their core behavior is already covered
by automated tests.

---

## Prerequisites

1. Automated tests pass before manual testing:

```bash
uv run pytest tests/ -q
```

Pass: no new failures beyond those already tracked in `docs/testLog.md`.

2. Frontend tests pass:

```bash
cd frontend && npm test
```

Pass: all Vitest tests pass.

3. Frontend production build passes:

```bash
cd frontend && npm run build
```

Pass: build completes without TypeScript or Vite errors.

4. Start the FastAPI and React servers in separate terminals:

```bash
# Terminal A, from repo root
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001

# Terminal B
cd frontend && npm run dev
```

Open http://localhost:5173 in a browser.

When a test says "stop FastAPI", press `Ctrl-C` in Terminal A. When it says
"restart FastAPI", rerun the Terminal A command from the repo root. Do not start
FastAPI from `frontend/`, because that creates/uses `frontend/neurodb.duckdb`.

5. Test data is available:

- At least one dataset exists in the Datasets panel.
- At least one pending Knowledge Library source exists.
- Suggestions includes one pending `learning_source` suggestion and one pending non-`learning_source` suggestion.
- Suggestions includes one pending import request for a dataset that can be imported by an available connector.

If a required row is missing, create it through the existing Tutor, Research, discovery, or local fixture workflows before running the relevant eval.

---

## Manual Evals

### T1 - Study tag create persists and remains searchable by agent tooling

Open Study Log. Select "Study Tags". Click "Add Tag".

Create a tag for an existing dataset with:

- source: the dataset source shown in Datasets
- source_id: the dataset id shown in Datasets
- concept_tag: `UI5-P1-manual-LTP`
- section_ref: `UI5-P1`
- note_text: `Manual UI-5 P1 study note for vector embedding verification`

Click Save.

Stop FastAPI in Terminal A. Keep React running in Terminal B.

Run:

```bash
uv run scripts/study.py --db neurodb.duckdb list --concept UI5-P1-manual-LTP
```

Then verify the note was embedded in the same ChromaDB collection used by the API:

```bash
uv run python tests/manual/ui5_p1_verify_vector_embedding.py
```

If `NEURODB_DB_PATH` is set to a non-default DB, the script uses the matching Chroma path (`<db_name>_chroma`). To override it explicitly, run:

```bash
uv run python tests/manual/ui5_p1_verify_vector_embedding.py --chroma-path <db_name>_chroma
```

Restart FastAPI from the repo root before continuing to T2 or any browser step.

**Pass:** The new tag appears in React and in the CLI output. The vector-store search prints a `note:` result containing `UI5-P1-manual-LTP`. No inline warning appears during normal operation.

**Fail:** The save fails, the tag is missing from either surface, the vector-store result is missing, or React shows a warning during normal ChromaDB operation.

### T2 - Study tag vector-store warning is visible if embedding fails

This failure path is primarily covered by automated tests. If a local fault-injection environment is available, repeat T1 with the API configured so `embed_note` fails after the DB row is created.

FastAPI must be running with the fault-injection configuration for the browser
save step. If you run any CLI inspection afterward, stop that FastAPI process
first, run the CLI, then restart the normal FastAPI backend from the repo root
before T3. React may remain running throughout.

**Pass:** The tag still appears in React, and React shows an inline warning beginning with `Vector embedding failed:`.

**Fail:** The whole create operation fails, the saved tag disappears, or no warning is shown after the induced embedding failure.

### T3 - Knowledge Library approve indexes approved source

Open Knowledge Library. Set the filter to pending or all. Choose a pending source and click Approve.

Stop FastAPI in Terminal A after the list refreshes. Keep React running.

After the list refreshes, run a query for the approved source id:

```bash
uv run scripts/query_cli.py --sql "SELECT id, status, chroma_id FROM knowledge_sources WHERE id = <SOURCE_ID>" --db neurodb.duckdb
```

Replace `<SOURCE_ID>` with the approved row id.

Restart FastAPI from the repo root before continuing to T4 or any browser step.

**Pass:** The row status is `approved`, `chroma_id` is populated, and no inline warning appears during normal operation.

**Fail:** Status remains pending, `chroma_id` is empty, or React shows a warning during normal ChromaDB operation.

### T4 - Knowledge Library warning is visible if indexing fails

This failure path is primarily covered by automated tests. If a local fault-injection environment is available, approve a pending Knowledge Library source with the API configured so `knowledge_store.add_summary` fails after the DB status update.

FastAPI must be running with the fault-injection configuration for the browser
approve step. If you run any CLI inspection afterward, stop that FastAPI process
first, run the CLI, then restart the normal FastAPI backend from the repo root
before T5. React may remain running throughout.

**Pass:** The source is still approved, and React shows an inline warning beginning with `ChromaDB indexing failed:`.

**Fail:** Approval fails completely, the source remains pending, or no warning is shown after the induced indexing failure.

### T5 - Dataset import marks the import queue row imported

Open Suggestions. Find a pending import request for a dataset that exists in the Datasets panel. Click Import.

Wait until the inline task status reaches "Import complete".

Stop FastAPI in Terminal A. Keep React running.

Run:

```bash
uv run scripts/query_cli.py --sql "SELECT source, source_id, status, resolved_at FROM import_queue WHERE source = '<SOURCE>' AND source_id = '<SOURCE_ID>' ORDER BY id DESC LIMIT 1" --db neurodb.duckdb
```

Replace `<SOURCE>` and `<SOURCE_ID>` with the imported row values.

Restart FastAPI from the repo root before continuing to T6 or any browser step.

**Pass:** React shows "Import complete"; the matching `import_queue` row has `status = imported` and a non-empty `resolved_at`.

**Fail:** The task remains running indefinitely, the task succeeds but the queue row remains pending, or `resolved_at` is empty.

### T6 - Promote is shown only for learning source suggestions

Ensure FastAPI is running from the repo root. React should still be running.

Open Suggestions and inspect pending source suggestions.

**Pass:** `learning_source` rows show Dismiss and Promote. Non-`learning_source` rows show Dismiss but do not show Promote.

**Fail:** Any dataset, connector, paper, or other non-`learning_source` suggestion shows Promote.

### T7 - Promote creates a user-attributed registry entry

Open Suggestions. For a pending `learning_source` suggestion, click Promote.

Open Registry and locate the promoted entry.

Stop FastAPI in Terminal A after confirming the Registry row is visible. Keep
React running.

Run:

```bash
uv run scripts/query_cli.py --sql "SELECT source_key, display_name, added_by FROM learning_sources WHERE source_key = '<SOURCE_KEY>'" --db neurodb.duckdb
```

Replace `<SOURCE_KEY>` with the promoted suggestion reference.

Restart FastAPI from the repo root before continuing to T8 or any browser step.

**Pass:** The promoted entry appears in Registry, the suggestion disappears from Suggestions, and `added_by` is `user`.

**Fail:** The entry is missing, the suggestion remains pending, or `added_by` is anything other than `user`.

### T8 - Registry add form stores topics and hides added_by

Open Registry. Click "Add Source".

Confirm the form has a topics field and no `added_by` field. Fill in:

- source_type: `paper`
- source_key: `doi:10.ui5-p1/manual-topics`
- display_name: `UI-5 P1 Manual Topics Source`
- topics: `LTP, plasticity`

Click Save.

Stop FastAPI in Terminal A after the Registry list refreshes. Keep React running.

Run:

```bash
uv run scripts/query_cli.py --sql "SELECT source_key, content_json, added_by FROM learning_sources WHERE source_key = 'doi:10.ui5-p1/manual-topics'" --db neurodb.duckdb
```

Restart FastAPI from the repo root if continuing manual exploration after T8.

**Pass:** The entry appears in Registry; `content_json` contains both `LTP` and `plasticity`; `added_by` is `user`.

**Fail:** The topics are missing, `content_json` is empty, the UI exposes `added_by`, or `added_by` is not `user`.

---

## Sign-Off

| Eval | Result | Notes |
|------|--------|-------|
| T1 - Study tag create persists and remains searchable | Pending | |
| T2 - Study tag embedding warning path | Pending | Automated coverage acceptable if no fault-injection environment is available |
| T3 - Knowledge Library approve indexes source | Pending | |
| T4 - Knowledge Library indexing warning path | Pending | Automated coverage acceptable if no fault-injection environment is available |
| T5 - Dataset import marks queue imported | Pending | |
| T6 - Promote hidden for non-learning sources | Pending | |
| T7 - Promote creates user-attributed registry entry | Pending | |
| T8 - Registry add stores topics and hardcodes user | Pending | |

**Signed off:** Pending
