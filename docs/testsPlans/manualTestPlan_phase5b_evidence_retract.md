# Manual Test Plan — Phase 5b: Evidence Lens, Dataset Honesty, and Retract Lifecycle

**Status:** Active — Phase 5b; T1-T4 passed, T5-T7 pending
**Date created:** 2026-05-21
**Spec:** `docs/superpowers/specs/2026-05-21-phase5b-evidence-lens-dataset-honesty-retract-design.md`

---

## Prerequisites

- [ ] Run automated tests: `uv run pytest tests/ -q`
  - Pass criterion: no new failures beyond those in `docs/testLog.md`
- [ ] Run frontend tests: `cd frontend && npm run test`
  - Pass criterion: all tests pass
- [ ] Start backend: `uv run uvicorn neurodb.api.app:app_factory --factory --reload --port 8000`
- [ ] Start frontend dev server: `cd frontend && npm run dev`
- [ ] Open browser to `http://localhost:5173`

---

## T1 — Evidence Lens: Contextual Mode

**Steps:**
1. Set agent mode to "Neuro Tutor", context mode to "Contextual".
2. Send: "What is long-term potentiation?"
3. Observe the assistant bubble after the response completes.
4. Locate the evidence `<details>` element below the response.
5. Click to expand it.

**Pass criteria:**
- A collapsed `<details>` element appears below the response text, labeled with mode and source counts
- Collapsed label format: `▸ Evidence: contextual · Np · Nn · Nc · Nd` (counts may be 0)
- Expanded body shows counts labeled clearly
- No evidence lens appears for Local DB or External DB turns

---

## T2 — Evidence Lens: Gap Warning

**Steps:**
1. Set agent mode to "Neuro Research", context mode to "Grounded".
2. Send: "What dataset evidence do I have for cortical remapping after stroke?"
3. Observe the collapsed evidence lens label.

**Pass criteria:**
- If `gaps > 0`, the collapsed label includes `· ⚠ N gap`
- Gap count is shown in amber in the expanded view

---

## T3 — Dataset Honesty: Usefulness Badge

**Steps:**
1. Open the Datasets panel.
2. Search for any keyword (try leaving it empty and pressing Search).
3. Observe dataset rows that have a research packet.

**Pass criteria:**
- Rows with `sparse` status show a red left border and "sparse — {gap note}" in the metadata column
- Rows with `partial` show an amber left border and "partial — {gap note}"
- Rows with `research_context_ready` or `analysis_ready` show a green left border and the state label
- Rows without a research packet render exactly as before (no border, no label)

---

## T4 — Research Questions: Archive Action

**Steps:**
1. Open the Research panel.
2. Confirm the Research Questions grouping can be collapsed and expanded.
3. Locate a research question with status "open".
4. Confirm the status chip appears before the question text, not in the far-right column.
5. Hover or focus the status chip and read the status explanation.
6. Click the status chip on that question.
7. Read the Archive action impact text.
8. Select "Archive" from the dropdown.

**Pass criteria:**
- Dropdown appears on chip click, showing "Archive"
- Status tooltip explains what "open" means
- Archive action explains that the item leaves the active workflow but remains auditable
- After clicking Archive, the question status updates to "archived" without a page reload
- The status chip color changes to muted/red

---

## T5 — Claims: Approve and Reject

**Steps:**
1. Open the Research panel.
2. Expand the Claims section.
3. Locate a claim with status "candidate".
4. Confirm the status chip appears before the claim text.
5. Hover or focus the candidate status chip and read the status explanation.
6. Click its status chip and read the Approve, Reject, and Archive action impact text.
7. Select "Approve".
8. Verify the status updates to "approved".
9. Click the chip again and select "Reject".
10. Verify the status updates to "rejected".

**Pass criteria:**
- Claims section is visible and lists claim cards
- Claims section can be collapsed and expanded
- Candidate status tooltip explains that the claim still needs review before it is trusted
- Dropdown action text explains the impact before selection
- Status chip transitions work without page reload
- Color coding: candidate = blue-grey, approved = green, rejected = red

---

## T6 — Gaps: Resolve and Archive

**Steps:**
1. Open the Research panel.
2. Expand the Gaps section.
3. Locate a gap with status "open".
4. Confirm the status chip appears before the gap description.
5. Hover or focus the open status chip and read the status explanation.
6. Click its status chip and read the Resolve and Archive action impact text.
7. Select "Resolve".
8. Verify the status updates to "resolved".

**Pass criteria:**
- Gaps section visible with gap cards
- Gaps section can be collapsed and expanded
- Open status tooltip explains that the gap still needs review or follow-up
- Dropdown action text explains the impact before selection
- Resolve transition works and status updates immediately

---

## T7 — Evidence Links: Retract

**Steps:**
1. Open the Research panel.
2. Confirm the Draft Hypotheses grouping can be collapsed and expanded.
3. Find a hypothesis and click "Details" to expand it.
4. Locate an evidence link in the expanded view.
5. Confirm the evidence link status chip appears before the link description.
6. Hover or focus the active status chip and read the status explanation.
7. Click its status chip and read the Retract action impact text.
8. Select "Retract".

**Pass criteria:**
- Evidence link status chip visible on each link in the expanded hypothesis view
- Active status tooltip explains that the link is currently counted in the evidence set
- Retract action explains that the link remains auditable but stops counting as active support
- Retract transitions the status to "retracted"
- Chip color changes to red/muted after retract

---

## Current Results

| Test | Result | Date | Notes |
|---|---|---|---|
| T1 — Evidence Lens: Contextual Mode | Pass | 2026-05-23 | User-reported manual pass |
| T2 — Evidence Lens: Gap Warning | Pass | 2026-05-23 | User-reported manual pass |
| T3 — Dataset Honesty: Usefulness Badge | Pass | 2026-05-23 | User-reported manual pass |
| T4 — Research Questions: Archive Action | Pass | 2026-05-23 | User-reported manual pass |
| T5 — Claims: Approve and Reject | Pending | — | |
| T6 — Gaps: Resolve and Archive | Pending | — | |
| T7 — Evidence Links: Retract | Pending | — | |

---

## Sign-Off

| Tester | Date | Result | Notes |
|---|---|---|---|
| | | | |
