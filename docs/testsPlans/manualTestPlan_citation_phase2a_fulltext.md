# Manual Test Plan — Citation-Grade (Phase 1 + Phase 2a) + Learning Plans (combined)

**Why combined:** three feature sets reached "implementation complete, manual verification pending" without a sign-off pass. This single plan runs all of them in one browser/server session so the app only has to be stood up once. The two citation-grade phases are ordered as in the data-tier arc — abstract grounding (Part A) before full text (Part B).

- **Part A — Citation-Grade Phase 1: Abstract Grounding (AG1–AG5):** abstract-grounded Knowledge Library summaries + data tier / vintage / currency disclosure.
  - Spec: `docs/superpowers/specs/2026-06-09-citation-grade-data-access-design.md` (Phase 1)
- **Part B — Citation-Grade Phase 2a: Full-Text RAG (FT1–FT8):** structured-source full-text acquisition, chunk/embed, quotable retrieval, fail-closed quote verification.
  - Spec: `docs/superpowers/specs/2026-06-10-citation-grade-phase2a-structured-fulltext-design.md`
- **Part C — Learning Plans (LP1–LP8):** agent-proposed multi-step study plans, the proposed→confirmed lifecycle, per-step progress, agent-proposed updates, grouping cross-reference, and the Study Plan "Plans" section.
  - Spec: `docs/superpowers/specs/2026-06-05-learning-plans-design.md` · Plan: `docs/superpowers/plans/2026-06-05-learning-plans.md`

**Status:** Pending verification · **Tester:** Eric Herrmann

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. **Automated suite green (run first).** No new failures beyond those tracked in `docs/testLog.md`:

   ```bash
   uv run pytest tests/ -q
   ```

   Pass: only the tracked pre-existing failures remain (at authoring: `test_neuro_atlas_data.py` ×2; 928 passed).

2. **Frontend gate.**

   ```bash
   cd frontend && npm test -- --run && npm run build
   ```

   Pass: all Vitest tests pass; the `tsc -b && vite build` build is clean.

3. **Start the backend** against a disposable DB so checks do not alter the main working DB:

   ```bash
   NEURODB_DB_PATH=neurodb_manual.duckdb \
     uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
   ```

4. **Start the frontend** (second terminal):

   ```bash
   cd frontend && npm run dev
   ```

   Open the dev URL Vite prints (default `http://localhost:5173`). Ensure `.env` holds a working model API key so the agents can run; a local Chroma store is created alongside the disposable DB for the citation parts.

> These cases cover the browser workflow, real server/DB/Chroma wiring, and agent
> tool-calling that the automated unit/integration tests do not exercise.

---

## Part A — Citation-Grade Phase 1 (Abstract Grounding)

### AG1 — Abstract captured on queue
In a **Neuro-Tutor** chat, run a literature search and have the agent queue a source that has an abstract. Open the Knowledge Library.
**Pass:** the queued paper row stores the abstract and year, and shows tier **abstract**.

### AG2 — Summary grounded in abstract
Approve the queued source.
**Pass:** the generated summary reflects content from the abstract (not just the title) — e.g. mentions a method/finding present in the abstract but not implied by the title.

### AG3 — Metadata-only paper
Queue a source with no abstract.
**Pass:** tier shows **metadata**, and the agent, when citing it, says it is orienting from metadata only.

### AG4 — Post-cutoff disclosure
Ask the agent about an approved source dated 2026 or later.
**Pass:** it states it has no training prior and relies on the stored text.

### AG5 — Currency warning
Flag an approved source as retracted (via the update path/DB), then ask the agent about it.
**Pass:** it surfaces a retraction warning instead of a clean citation.

**Part A pass/fail:** all of AG1–AG5 behave as described; no regression in existing queue/approve/search flows.

---

## Part B — Citation-Grade Phase 2a (Full-Text RAG)

### FT1 — Acquire arXiv full text
Approve a paper whose URL is an arXiv abstract page. Click **Acquire full text**.
**Pass:** the tier badge becomes **full text** and status shows **verified**.

### FT2 — Acquire PMC (OA) full text
Same for a PMC open-access paper (JATS).
**Pass:** **full text** / **verified**.

### FT3 — Non-OA / publisher HTML rejected
Acquire a paper whose URL is a publisher HTML/PDF page.
**Pass:** it stays at **abstract** tier, status **unavailable**, and the Phase-2b deferral message is shown.

### FT4 — User-supplied text
Paste/upload `.md` text for a paper with no fetchable source.
**Pass:** **full text** / **verified**.

### FT5 — Grounded quote
In a **Neuro-Tutor** chat, ask the agent to quote a passage from a verified paper.
**Pass:** the quote renders with a source + section anchor and a `[verified]` marker.

### FT6 — Honest absence
Ask the agent to quote about a topic absent from any acquired paper.
**Pass:** it states it has no grounded full-text support rather than inventing a quote.

### FT7 — Unverified backstop
Induce the agent to present a quote it did not verify (e.g., a paraphrase in quotes).
**Pass:** the response carries the ⚠ unverified notice.

### FT8 — Idempotent re-acquire
Re-run **Acquire full text** on a verified paper.
**Pass:** no duplicate chunks (chunk count unchanged) and status stays **verified**.

**Part B pass/fail:** all of FT1–FT8 behave as described; no regression in queue/approve/search flows.

---

## Part C — Learning Plans

### LP1 — Tutor proposes a plan
In a **Neuro-Tutor** chat, explore a topic (e.g. long-term potentiation) and ask for a multi-step study plan. Open the Study Plan → **Plans**.
**Pass:** a card appears with status **PROPOSED**, the proposed steps are listed in the detail view, and suggested topic chips are present.

### LP2 — Research agent proposes a plan
Repeat LP1 from a **Research** agent chat.
**Pass:** a new plan appears whose `origin_agent` is `research` (confirm via `GET /api/research/plans` if needed).

### LP3 — Confirm a proposed plan
Click **Confirm** on a proposed plan that contains at least one `read` step.
**Pass:** status changes to **ACTIVE**; the read step's source now appears in the Knowledge Library (queued/pending); the read step still displays the source title in the plan detail view; topic chips are confirmable.

### LP4 — Dismiss leaves no artifacts
On a *different* proposed plan that contains a `read` step, click **Dismiss**.
**Pass:** the plan disappears from the list, and its read source did **not** appear in the Knowledge Library.

### LP5 — Step progress drives completion
On an active plan, change confirmed-step progress controls (`todo` → `in_progress` → `done`, and one to `skipped`).
**Pass:** the % complete bar updates; a `skipped` step is excluded from the denominator (does not lower completion).

### LP6 — Agent proposes an update
Ask an agent to add and/or remove a step on an existing active plan.
**Pass:** the detail view shows pending additions (and struck-through `proposed_removal` steps) with a pending-changes badge. **Confirm changes** applies them; **Dismiss changes** reverts (additions dropped, removals kept).

### LP7 — Cross-reference
Create two plans that share a topic and confirm that topic on both.
**Pass:** the shared topic surfaces as appearing across both plans (`GET /api/research/plans/{id}` groupings + the cross-reference count).

### LP8 — Edit / pause / delete
From the Study Plan panel, rename a plan, pause it, then delete it.
**Pass:** the title and status update; the plan is removed after delete.

**Part C pass/fail:** all of LP1–LP8 behave as described.

---

## Sign-off

| Case | Result | Notes |
|------|--------|-------|
| AG1  |        |       |
| AG2  |        |       |
| AG3  |        |       |
| AG4  |        |       |
| AG5  |        |       |
| FT1  |        |       |
| FT2  |        |       |
| FT3  |        |       |
| FT4  |        |       |
| FT5  |        |       |
| FT6  |        |       |
| FT7  |        |       |
| FT8  |        |       |
| LP1  |        |       |
| LP2  |        |       |
| LP3  |        |       |
| LP4  |        |       |
| LP5  |        |       |
| LP6  |        |       |
| LP7  |        |       |
| LP8  |        |       |
