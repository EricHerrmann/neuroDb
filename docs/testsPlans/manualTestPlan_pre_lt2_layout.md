# Pre-LT-2: Chat Layout Hardening — Manual Test Plan

**Feature:** Fixed-pane layout, input pinned to bottom, sidebar migration
**Status:** Pending manual sign-off
**Spec:** `docs/superpowers/specs/2026-05-05-pre-lt2-chat-layout-hardening.md`
**Date:** 2026-05-05

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. `.env` has `ANTHROPIC_API_KEY` set.
2. Automated tests pass before manual testing:

```bash
uv run pytest tests/ -q --tb=no
```

Expected: `264 passed`.

3. Start the app:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

4. Open `http://localhost:8501` in a browser.

---

## T1 — Input stays visible as conversation grows

1. Send 6+ messages until the transcript is longer than the viewport.
2. **Pass:** The text input and Send/Clear buttons remain visible at the bottom without scrolling the page.
3. **Fail:** The input scrolls off the bottom of the screen.

---

## T2 — Transcript scrolls within its pane

1. With multiple messages in the transcript, scroll up within the transcript area.
2. **Pass:** Only the transcript scrolls; the input area stays pinned below it.
3. **Fail:** Scrolling moves the whole page rather than just the transcript.

---

## T3 — Right workspace pane is always accessible

1. Send several messages until the transcript is long.
2. Without any page scroll, click through Suggestions, Study Log, Datasets, Registry, Knowledge Library, and SQL tabs in the right pane.
3. **Pass:** All tabs are reachable; no page scrolling required.
4. **Fail:** Tabs are cut off or require page scroll to reach.

---

## T4 — Right workspace pane scrolls independently

1. Open the Datasets tab. If the dataset list is long, scroll down within it.
2. **Pass:** Only the Datasets list scrolls; the chat pane and tab bar stay fixed.
3. **Fail:** Scrolling the right pane scrolls the whole page.

---

## T5 — Mode toggle in sidebar

1. Locate the Agent section in the left sidebar.
2. Switch between Local DB, External DB, and Neuro-Tutor using the radio.
3. **Pass:** Mode changes take effect; the radio is in the sidebar, not in the main chat panel.
4. **Fail:** Radio is absent from the sidebar, or still appears inside the chat panel.

---

## T6 — Chapter context controls in sidebar

1. Switch to Local DB mode. Open the Context section in the sidebar.
2. Select a textbook and type `Ch12`.
3. Click `Set chapter context`.
4. **Pass:** Active context caption appears in the sidebar; the chat panel has no chapter controls.
5. **Fail:** Chapter controls are missing from the sidebar, or appear inside the chat panel.

---

## T7 — Sidebar collapse reflows columns

1. Click the Streamlit sidebar collapse arrow.
2. **Pass:** Both chat and workspace columns expand proportionally to fill available width.
3. **Fail:** Columns stay narrow or overlap when sidebar is collapsed.

---

## T8 — Auto-scroll after agent response

1. Send a message that produces a multi-paragraph response.
2. Before the response lands, scroll the transcript up.
3. **Pass:** After the response finishes, the transcript scrolls back to the newest message.
4. **Note:** Auto-scroll uses JavaScript injection and may not fire in all browser security contexts. If it does not scroll automatically, confirm that the input remains visible and note the browser/OS. This test does not block sign-off by itself.

---

## Sign-off

| Test | Result | Notes |
|------|--------|-------|
| T1 | | |
| T2 | | |
| T3 | | |
| T4 | | |
| T5 | | |
| T6 | | |
| T7 | | |
| T8 | | |

**Signed off by:** ___  **Date:** ___
