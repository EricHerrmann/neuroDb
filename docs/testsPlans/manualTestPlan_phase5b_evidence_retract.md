# Manual Test Plan — Phase 5b: Evidence Lens, Dataset Honesty, and Retract Lifecycle

**Status:** Active — Phase 5b
**Date created:** 2026-05-21
**Spec:** `docs/superpowers/specs/2026-05-21-phase5b-evidence-lens-dataset-honesty-retract-design.md`

---

## Prerequisites

- [ ] Run automated tests: `uv run pytest tests/ -q`
  - Pass criterion: no new failures beyond those in `docs/testLog.md`
- [ ] Run frontend tests: `cd frontend && npm run test`
  - Pass criterion: all tests pass
- [ ] Start backend: `uv run uvicorn src.neurodb.api.app:app --reload --port 8000`
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
2. Locate a research question with status "open".
3. Click the status chip on that question.
4. Select "Archive" from the dropdown.

**Pass criteria:**
- Dropdown appears on chip click, showing "Archive"
- After clicking Archive, the question status updates to "archived" without a page reload
- The status chip color changes to muted/red

---

## T5 — Claims: Approve and Reject

**Steps:**
1. Open the Research panel.
2. Expand the Claims section.
3. Locate a claim with status "candidate".
4. Click its status chip and select "Approve".
5. Verify the status updates to "approved".
6. Click the chip again and select "Reject".
7. Verify the status updates to "rejected".

**Pass criteria:**
- Claims section is visible and lists claim cards
- Status chip transitions work without page reload
- Color coding: candidate = blue-grey, approved = green, rejected = red

---

## T6 — Gaps: Resolve and Archive

**Steps:**
1. Open the Research panel.
2. Expand the Gaps section.
3. Locate a gap with status "open".
4. Click its status chip and select "Resolve".
5. Verify the status updates to "resolved".

**Pass criteria:**
- Gaps section visible with gap cards
- Resolve transition works and status updates immediately

---

## T7 — Evidence Links: Retract

**Steps:**
1. Open the Research panel.
2. Find a hypothesis and click "Details" to expand it.
3. Locate an evidence link in the expanded view.
4. Click its status chip and select "Retract".

**Pass criteria:**
- Evidence link status chip visible on each link in the expanded hypothesis view
- Retract transitions the status to "retracted"
- Chip color changes to red/muted after retract

---

## Sign-Off

| Tester | Date | Result | Notes |
|---|---|---|---|
| | | | |
