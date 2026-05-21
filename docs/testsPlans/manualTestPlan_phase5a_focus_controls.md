# Manual Test Plan — Phase 5a: Focus Controls and Agent In-Progress Feedback

**Status:** Active — Phase 5a
**Date created:** 2026-05-21
**Spec:** `docs/superpowers/specs/2026-05-21-phase5a-focus-controls-design.md`

---

## Prerequisites

- [ ] Run automated tests: `cd frontend && npm run test`
  - Pass criterion: all tests pass (no new failures)
- [ ] Run backend unit tests: `uv run pytest tests/ -q`
  - Pass criterion: no new failures beyond those tracked in `docs/testLog.md`
- [ ] Start backend: `uv run uvicorn src.neurodb.api.app:app --reload --port 8000`
- [ ] Start frontend dev server: `cd frontend && npm run dev`
- [ ] Open browser to `http://localhost:5173`

---

## T1 — Models Dropdown: Read-Only Tier Display

**What:** The Models dropdown replaces the three inline model-tier text labels. It opens to show Low / Mid / High → model name mappings. No option is selectable.

**Steps:**
1. Open the app. Observe the chat header.
2. Confirm the three text spans "Low: …", "Mid: …", "High: …" are gone.
3. Locate the Models dropdown (leftmost of the three dropdowns, to the right of Clear).
4. Click the Models dropdown to open it.
5. Observe the three options displayed.

**Pass criteria:**
- Inline text labels are absent from the header.
- The dropdown label reads "Models" (or similar placeholder).
- Three disabled options appear: "Low → {model}", "Mid → {model}", "High → {model}".
- No option is selectable / clicking an option does not change the displayed value.

---

## T2 — Context Mode Dropdown: Visible for Neuro Agents

**What:** Context mode dropdown appears only when agent mode is `neuro_tutor` or `neuro_research`.

**Steps:**
1. Set agent mode to "Neuro Tutor" via the agent mode dropdown.
2. Observe the header for a third dropdown (rightmost).
3. Change agent mode to "Neuro Research".
4. Observe the header again.

**Pass criteria:**
- Context mode dropdown is visible for both Neuro Tutor and Neuro Research.
- The dropdown displays one of "General", "Contextual", or "Grounded" as the selected value.
- The dropdown has a blue border/tint that distinguishes it from the other dropdowns.

---

## T3 — Context Mode Dropdown: Hidden for DB Agents

**What:** Context mode dropdown is absent when agent mode is `local_db` or `external_db`.

**Steps:**
1. Change agent mode to "Local DB".
2. Observe the header — count the dropdowns.
3. Change agent mode to "External DB".
4. Observe the header again.

**Pass criteria:**
- Only two dropdowns (Models + Agent Mode) are visible for both Local DB and External DB.
- No context mode dropdown appears.

---

## T4 — Context Mode Dropdown: Persists Selection

**What:** Selecting a context mode writes to the API and persists the value on page reload.

**Steps:**
1. Set agent mode to "Neuro Tutor".
2. Note the current context mode in the dropdown.
3. Select a different mode (e.g., change from "Contextual" to "Grounded").
4. Open browser DevTools → Network. Verify a `PUT /api/preferences/context-mode` request fired with the correct body `{"mode": "grounded"}`.
5. Reload the page.
6. Return to Neuro Tutor agent mode and check the context mode dropdown.

**Pass criteria:**
- Network tab shows the PUT request with correct payload.
- After reload, the context mode dropdown shows the value that was selected before reload.

---

## T5 — Context Mode Tooltip: Hover Shows Description

**What:** Hovering the context mode dropdown (or its wrapper) shows a tooltip describing the current mode.

**Steps:**
1. Set agent mode to "Neuro Tutor".
2. Hover the mouse over the context mode dropdown.
3. Note the tooltip text.
4. Change context mode to "General". Hover again.
5. Change context mode to "Grounded". Hover again.

**Pass criteria:**
- **General:** tooltip reads "Model knowledge only. Use before you have local data on a topic."
- **Contextual:** tooltip reads "NeuroDb context prepended. Use when working with ingested data."
- **Grounded:** tooltip reads "Local evidence only. Names missing sources instead of filling gaps. Use for hypothesis work."
- Tooltip disappears when mouse leaves the element.

---

## T6 — Behavioral Difference Across Context Modes

**What:** Sending the same message under different context modes produces visibly different responses.

**Steps:**
1. Set agent mode to "Neuro Tutor".
2. Set context mode to "General". Send: "What do you know about LTP in hippocampal neurons?"
3. Note response length and whether it mentions local data.
4. Clear chat. Set context mode to "Contextual". Send the same message.
5. Note whether the response references ingested data.
6. Clear chat. Set context mode to "Grounded". Send the same message.
7. Note whether the response names missing sources or explicitly limits itself to local evidence.

**Pass criteria:**
- General: responds from model knowledge, no reference to NeuroDb local data.
- Contextual: response shows awareness of ingested context (or indicates none is available).
- Grounded: response explicitly limits itself to local evidence; if data is missing, it says so rather than filling from model knowledge.

---

## T7 — In-Progress Feedback: Dead Zone 1 (Submit → First SSE Event)

**What:** After submitting a message, "Thinking ···" appears in the assistant bubble before any content arrives.

**Steps:**
1. Set agent mode to "Neuro Tutor".
2. In DevTools, throttle network to "Slow 3G" (or use browser's network conditions).
3. Submit a message: "What is synaptic plasticity?"
4. Watch the chat area immediately after clicking Send.

**Pass criteria:**
- An assistant bubble appears instantly after submit with "Thinking ···" (animated dots).
- The bubble does not remain blank/empty before text arrives.
- Once text starts streaming, "Thinking ···" transitions to the streaming text.

---

## T8 — In-Progress Feedback: Dead Zone 2 (Tool Executing)

**What:** When a tool call fires, the assistant bubble shows the tool name with animated dots.

**Steps:**
1. Set agent mode to "Neuro Research".
2. Submit a message that triggers a tool: "Get the topic bundle for neuroplasticity."
3. Watch the assistant bubble during execution.

**Pass criteria:**
- After "Thinking ···" (DZ1), the bubble transitions to "▸ {tool_name} ···".
- If multiple tools run, the name updates to the current tool on each new tool call.
- Once text starts streaming, the tool indicator clears and normal text renders.

---

## T9 — Tool Trace Still Available After Completion

**What:** The existing collapsed `<details>` tool activity pane remains available after a response that used tools.

**Steps:**
1. Complete a tool-calling response (e.g., the same message from T8).
2. After the response finishes streaming, locate the `<details>` element in the assistant bubble.
3. Click to expand it.

**Pass criteria:**
- The `<details>` section is collapsed by default after completion.
- Expanding it shows the full tool trace (tool name, status).

---

## T10 — Full Flow: Header + In-Progress + Completion

**What:** End-to-end golden path confirming all P5a features work together.

**Steps:**
1. Set agent mode to "Neuro Research", context mode to "Contextual".
2. Verify: Models dropdown present, Agent Mode shows "Neuro Research", Context Mode shows "Contextual" with blue border.
3. Submit: "List open research questions for my current topic."
4. Watch: "Thinking ···" → tool name → streaming text → complete.
5. Confirm the `<details>` tool trace is present after completion.
6. Switch agent mode to "Local DB".
7. Confirm: context mode dropdown disappears from header.

**Pass criteria:**
- All header elements correct before submit.
- In-progress states visible and sequential during execution.
- Tool trace available after completion.
- Context mode dropdown disappears on switch to Local DB.

---

## Sign-Off

| Tester | Date | Result | Notes |
|---|---|---|---|
| | | | |
