# Manual Test Plan - UI-5 P2: Core Workflow

**Epoch scope:** UI - React core workflow parity across chat, study log,
datasets, research, and knowledge library.
**Phase:** UI-5 P2
**Design source:** `docs/superpowers/specs/2026-05-13-ui5-p2-core-workflow-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-05-13-ui5-p2-core-workflow.md`
**Status:** Superseded by `docs/testsPlans/manualTestPlan_ui5_common_parity.md`
**Date:** 2026-05-13
**Last updated:** 2026-05-13

This P2-only plan is retained for historical detail. Active UI-5 manual
verification now uses one common plan across P1, P2, and P3:
`docs/testsPlans/manualTestPlan_ui5_common_parity.md`.

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

**Automation boundary:** Automated tests own route logic, component branches,
fault injection, and task-state edge cases. Manual checks verify browser
workflow, FastAPI wiring, DuckDB/Chroma side effects, task visibility, and
readability in the real React shell.

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

4. Start FastAPI and React in separate terminals:

```bash
# Terminal A, from repo root
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001

# Terminal B
cd frontend && npm run dev
```

Open http://localhost:5173 in a browser.

---

## Manual Evals

### T1 - Chat responses and activity remain readable

Open Chat. Ask a question that causes tool use, such as asking for local
datasets related to a concept.

**Pass:** The assistant answer is readable in the chat bubble; tables/lists
render cleanly if present; tool activity is visible in a compact expandable area
or otherwise does not pollute the answer bubble.

### T2 - Chat clear ends the session

Send at least three user turns. Click Clear.

**Pass:** The chat clears only after the backend succeeds, and Study Log session
history shows a session row with a summary/topic when provider configuration is
available.

### T3 - Study Log delete and filters

Create a study tag, filter by its concept and source, then remove it.

**Pass:** The filters narrow the visible rows, Remove deletes the row from React,
and reloading the panel does not bring the row back.

### T4 - Dataset modality filter and metadata

Open Datasets. Filter by at least one modality.

**Pass:** Dataset rows show title/source/modality/subject count where available,
and selected modality narrows the result list.

### T5 - Research filters, hypothesis details, and review actions

Open Research. Toggle question and hypothesis status filters. Expand a
hypothesis with structured fields. For a pending review, accept or dismiss it.

**Pass:** Filters update lists predictably, expanded hypotheses show scientific
details, and accepted/dismissed reviews update without a full page reload.

### T6 - Knowledge Library duplicate check and summary task

Approve a pending Knowledge Library source.

**Pass:** If a near duplicate exists, React warns before approving. Approval shows
a task state while summary/indexing runs, then the row refreshes with approved
status and summary/chroma state when dependencies are available.
