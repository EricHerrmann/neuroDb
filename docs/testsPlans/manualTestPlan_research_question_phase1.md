# Manual Test Plan — Research Question Phase 1: Capture & Categorize

**Phase:** Research Question Phase 1
**Spec:** `docs/superpowers/specs/2026-06-01-research-question-phase1-design.md`
**Status:** Not started

---

## Prerequisites

- [ ] Run automated tests: `uv run pytest tests/ -q`
  Pass criterion: no new failures beyond those tracked in `docs/testLog.md`.
- [ ] Start the dev server: `uv run neurodb serve` (backend) + `cd frontend && npm run dev`

---

## T1 — Create a question from the UI

**Steps:**
1. Open ResearchPanel.
2. Fill in the question text area with: "Do biological memory systems and transformer attention share a common retrieval mechanism?"
3. Optionally fill topic_context with: "neuroscience and AI convergence".
4. Click Submit.

**Pass criteria:**
- Question appears in the question list immediately with status `open`.
- Within a few seconds, pending topic/concept suggestion chips appear below the question row.
- No page spinner or error toast.

---

## T2 — Confirm a suggested topic chip

**Steps:**
1. After T1, locate a pending topic chip on the question row.
2. Click "Confirm" on the chip.

**Pass criteria:**
- The chip is replaced by a confirmed topic badge.
- `GET /api/research/questions/{id}` (via browser DevTools or SQL panel) shows the topic with status `confirmed`.

---

## T3 — Dismiss a suggested topic chip

**Steps:**
1. After T1, locate a pending topic chip on the question row.
2. Click "Dismiss" on the chip.

**Pass criteria:**
- The chip disappears from the row.
- The topic no longer appears in the question's topic list.

---

## T4 — Filter question list by topic

**Steps:**
1. Confirm at least one topic on a question (T2).
2. Select that topic in the topic filter bar.

**Pass criteria:**
- Only questions with that confirmed topic are shown.
- Removing the filter restores all questions.

---

## T5 — Collapse and expand the question list

**Steps:**
1. Click "Collapse" on the Questions section header.
2. Click "Expand".

**Pass criteria:**
- Questions section collapses and the list disappears.
- Expanding restores all rows.
- State does not persist across page reload (local component state only).

---

## T6 — Delete a question

**Steps:**
1. Click the Delete control on any question row.
2. Confirm the prompt.

**Pass criteria:**
- Confirmation prompt appears before deletion.
- Question is removed from the list after confirmation.
- `GET /api/research/questions/{id}` returns 404.
- Cancelling the prompt leaves the question in place.
