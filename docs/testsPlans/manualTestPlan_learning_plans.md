# Learning Plans Manual Test Plan

**Epoch scope:** Research — tests agent-proposed multi-step study plans, the
proposed→confirmed lifecycle, per-step progress, agent-proposed updates,
grouping cross-reference, and the Study Plan "Plans" section.

**Status:** Pending verification
**Tester:** Eric Herrmann
**Scope:** `learning_plans`/`plan_steps` data model, `propose_learning_plan` /
`update_learning_plan` tools on both the tutor and research agents, the
`/api/research/plans` routes, and the Study Plan panel.

**Design spec:** `docs/superpowers/specs/2026-06-05-learning-plans-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-06-05-learning-plans.md`

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. **Automated gate (run first).** Backend suite must show no new failures
   beyond those tracked in `docs/testLog.md`:

   ```bash
   uv run pytest tests/ -q
   ```

   Pass: all tests pass (baseline at authoring: 838 passed, 0 failed).

2. **Frontend gate.**

   ```bash
   cd frontend && npm test && npm run build
   ```

   Pass: all Vitest tests pass; the `tsc -b && vite build` build is clean.

3. **Start the backend** against a disposable DB so checks do not alter the main
   working DB:

   ```bash
   NEURODB_DB_PATH=neurodb_lp_manual.duckdb \
     uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
   ```

4. **Start the frontend** (in a second terminal):

   ```bash
   cd frontend && npm run dev
   ```

   Open the dev URL Vite prints (default `http://localhost:5173`). Ensure the
   `.env` holds a working model API key so the agents can run.

> These manual cases cover the browser workflow, real server/DB wiring, and
> agent tool-calling that the automated unit/integration tests do not exercise.

---

## Cases

### T1 — Tutor proposes a plan
In a **Neuro-Tutor** chat, explore a topic (e.g. long-term potentiation) and ask
for a multi-step study plan. Open the Study Plan → **Plans**.
**Pass:** a card appears with status **PROPOSED**, the proposed steps are listed
in the detail view, and suggested topic chips are present.

### T2 — Research agent proposes a plan
Repeat T1 from a **Research** agent chat.
**Pass:** a new plan appears whose `origin_agent` is `research` (confirm via
`GET /api/research/plans` if needed).

### T3 — Confirm a proposed plan
Click **Confirm** on a proposed plan that contains at least one `read` step.
**Pass:** status changes to **ACTIVE**; the read step's source now appears in the
Knowledge Library (queued/pending); the read step still displays the source
title in the plan detail view; topic chips are confirmable.

### T4 — Dismiss leaves no artifacts
On a *different* proposed plan that contains a `read` step, click **Dismiss**.
**Pass:** the plan disappears from the list, and its read source did **not**
appear in the Knowledge Library.

### T5 — Step progress drives completion
On an active plan, change confirmed-step progress controls (`todo` →
`in_progress` → `done`, and one to `skipped`).
**Pass:** the % complete bar updates; a `skipped` step is excluded from the
denominator (does not lower completion).

### T6 — Agent proposes an update
Ask an agent to add and/or remove a step on an existing active plan.
**Pass:** the detail view shows pending additions (and struck-through
`proposed_removal` steps) with a pending-changes badge. **Confirm changes**
applies them; **Dismiss changes** reverts (additions dropped, removals kept).

### T7 — Cross-reference
Create two plans that share a topic and confirm that topic on both.
**Pass:** the shared topic surfaces as appearing across both plans
(`GET /api/research/plans/{id}` groupings + the cross-reference count).

### T8 — Edit / pause / delete
From the Study Plan panel, rename a plan, pause it, then delete it.
**Pass:** the title and status update; the plan is removed after delete.

---

## Sign-off

| Case | Result | Notes |
|------|--------|-------|
| T1   |        |       |
| T2   |        |       |
| T3   |        |       |
| T4   |        |       |
| T5   |        |       |
| T6   |        |       |
| T7   |        |       |
| T8   |        |       |
