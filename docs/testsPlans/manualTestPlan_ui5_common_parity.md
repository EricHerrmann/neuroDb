# Manual Test Plan - UI-5 Common Parity

**Epoch scope:** UI - React parity and polish across UI-5 P1, P2, and P3.
**Phases covered:** UI-5 P1 data integrity, UI-5 P2 core workflow, UI-5 P3 polish.
**Design sources:** `docs/superpowers/specs/2026-05-12-ui5-p1-data-integrity-design.md`, `docs/superpowers/specs/2026-05-13-ui5-p2-core-workflow-design.md`, `docs/superpowers/specs/2026-05-13-ui5-p3-polish-design.md`
**Status:** Ready for execution as the active consolidated UI-5 manual plan.
**Date:** 2026-05-13
**Last updated:** 2026-05-13

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

**Automation boundary:** Automated tests own route logic, component branches,
fault injection, and edge cases. This manual plan verifies the integrated
browser, FastAPI, DuckDB, and ChromaDB behavior that only appears when the full
React workbench is running.

---

## Prerequisites

1. Automated tests pass before manual testing:

```bash
uv run pytest tests/ -q
```

Pass: no new failures beyond those already tracked in `docs/testLog.md`.

2. Frontend tests pass:

```bash
cd frontend
npm test
```

Pass: all Vitest tests pass.

3. Frontend production build passes:

```bash
cd frontend
npm run build
```

Pass: build completes without TypeScript or Vite errors.

4. Stop any process that already holds `neurodb.duckdb`, then start FastAPI from
the project root:

```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
```

Pass: FastAPI starts without a DuckDB lock error. If a lock exists, stop the old
Python process before continuing.

5. Start React in a separate terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in a browser.

6. For CLI/DB spot checks, stop FastAPI first so DuckDB can be opened by the
script. React may remain running, but API-backed panels will show proxy errors
until FastAPI is restarted.

---

## Manual Evals

### T1 - P1 Study Log writes persist to DuckDB and ChromaDB

In Study Log, create a tag with:

- source: `openneuro`
- source_id: an existing dataset id
- concept_tag: `UI5-common-manual-LTP`
- section_ref: `UI5-common`
- note_text: `Manual UI-5 common study note for vector embedding verification`

Stop FastAPI, then run:

```bash
uv run scripts/study.py --db neurodb.duckdb list --concept UI5-common-manual-LTP
uv run tests/manual/ui5_p1_verify_vector_embedding.py --db neurodb.duckdb --concept UI5-common-manual-LTP
```

Pass: the tag appears in CLI output and vector search returns a matching note.
No inline warning appears during normal operation.

### T2 - P1 Knowledge and registry writes keep provenance and status

Approve a pending Knowledge Library source, import a queued dataset suggestion,
promote a learning-source suggestion, and add a Registry source with topics.

Pass: approved knowledge sources get approved status and Chroma/summary state
when dependencies are available; import queue item resolves to imported; only
learning-source suggestions expose Promote; promoted and manually added registry
sources show `added_by=user`; added topics remain visible after reload.

### T3 - P2 Chat is readable and observable

Open Chat and ask a question that uses tools, such as a local dataset or study
log lookup. Send at least three user turns, then click Clear.

Pass: the final answer renders readable prose/tables/lists instead of raw
Markdown artifacts; tool activity is visible but does not pollute the answer
bubble; Clear succeeds through the backend and the ended session appears in
Study Log/session history with summary/topic when provider configuration allows.

### T4 - P2 Study Log and Datasets support everyday cleanup and filtering

Create a temporary Study Log tag, filter by concept and source, remove it, then
reload. In Datasets, filter by modality and inspect at least three rows.

Pass: filters compose predictably; Remove deletes the row and it does not return
after reload; dataset rows show title/source/modality/subject count where
available; modality filtering narrows the list.

### T5 - P2 Research and Knowledge Library lifecycle actions work

In Research, toggle question and hypothesis status filters, expand a hypothesis,
then accept or dismiss a pending review. In Knowledge Library, approve a source
that has a near duplicate if available.

Pass: research filters update lists without stale rows; expanded hypotheses show
scientific detail fields; review actions update status without full page reload;
duplicate warnings appear before approval and approval shows task progress.

### T6 - P3 Chat and SQL polish are present

After P3 implementation, arrange for an active prior topic or use a seeded test
session that exposes one. Open Chat, then open SQL.

Pass: Chat shows a compact prior-context banner only when a prior topic exists;
SQL opens with `SELECT * FROM v_dataset_summary ORDER BY n_datasets DESC;` and
shows a useful table/view catalog hint.

### T7 - P3 Study Log edit and Dataset inline tag work

Select an existing Study Log row, edit its concept or note text, save, and
reload. Then tag a dataset directly from a Datasets result row.

Pass: selecting a Study Log row pre-fills the form; Save updates the existing
row rather than creating a duplicate; Cancel/Escape returns to add mode; inline
dataset tagging creates a Study Log row and surfaces any embedding warnings.

### T8 - P3 Registry and Knowledge Library detail polish is visible

Open Registry entries with `content_json` topics or chapters. Open Knowledge
Library entries with a DOI.

Pass: Registry cards expand to show topics or book chapters without breaking
items that lack content; bare DOI values link to `https://doi.org/...`; URL DOI
values remain clickable; non-DOI text remains plain.

---

## Completion Criteria

UI-5 common manual verification can be signed off only when T1-T8 pass against
the same local app stack, or when any remaining failures are logged in
`docs/testLog.md` and explicitly deferred in `docs/projectStatus.md`.
