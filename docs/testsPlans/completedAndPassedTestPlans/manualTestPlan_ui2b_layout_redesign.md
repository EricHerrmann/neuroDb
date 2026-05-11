# Manual Test Plan - UI-2B: Layout Redesign

**Epoch scope:** UI — activity rail, resizable/collapsible right panel, agent mode in chat header, chat history in Study Log.
**Phase:** UI-2B
**Design source:** `docs/superpowers/specs/2026-05-11-ui2b-layout-redesign.md`
**Implementation plan:** `docs/superpowers/plans/2026-05-11-ui2b-layout-redesign.md`
**Status:** Signed off - 2026-05-11
**Date:** 2026-05-11

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. Automated Python tests pass — no new failures beyond those tracked in `docs/testLog.md`:

```bash
uv run pytest tests/ -q
```

2. Automated frontend tests pass (19 tests):

```bash
cd frontend && npm test
```

3. Start both servers:

```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
cd frontend && npm run dev
```

Open http://localhost:5173 in a browser.

---

## Layout Evals

### T1 - Activity rail replaces sidebar

Open the app. Confirm there is no sidebar column. A 40px icon column is visible on the far left edge.

**Pass:** Sidebar is gone. Icon rail is present.

### T2 - Rail icons navigate to panels

Click each of the 7 rail icons: Suggestions, Study Log, Datasets, Registry, Knowledge Library, Research, SQL.

**Pass:** Each click loads the corresponding panel in the right column without a page reload.

### T3 - Active rail icon is highlighted

Click a rail icon. Confirm that icon has a blue background; all others are dark.

**Pass:** Active icon is `#3b82f6`; inactive icons are muted.

### T4 - Agent mode select in chat header

Confirm the chat panel has a header bar with a "CHAT" label on the left and an agent mode `<select>` on the right. Change the mode via the select.

**Pass:** Select is present, renders the four modes, and the change is reflected (page re-fetches preferences).

### T5 - Separator drag resizes panels

Drag the vertical separator between chat and right panel left and right.

**Pass:** Both panels resize proportionally as the separator moves.

### T6 - Right panel collapses; separator turns blue

Drag the separator fully to the right edge until the right panel disappears.

**Pass:** Right panel collapses to zero width. The separator bar turns blue (`#3b82f6`).

### T7 - Rail click re-expands collapsed panel

With the right panel collapsed (T6), click any rail icon.

**Pass:** Right panel re-expands and shows the selected panel content. Separator returns to dark.

### T8 - Chat streaming still works

Send a message in the chat input.

**Pass:** The assistant response streams in visibly and completes without error.

### T9 - Study Log: Chat History view

Open the Study Log panel. Change the dropdown from "Study Tags" to "Chat History".

**Pass:** Chat History view renders past sessions (or an empty-state message if no sessions exist). Each card shows topic, date, agent mode, and message count.

---

## Sign-off

| Eval | Result | Notes |
|------|--------|-------|
| T1 - Activity rail present | Pass | Sidebar deleted; 40px rail rendered at left edge |
| T2 - Rail navigation | Pass | All 7 panels navigated without error |
| T3 - Active icon highlight | Pass | Blue active state confirmed |
| T4 - Agent mode select | Pass | Select present in chat header; mode change round-trips to backend |
| T5 - Separator drag resize | Pass | Both panels resize on drag |
| T6 - Collapse to zero | Pass | Right panel collapses; separator turns blue |
| T7 - Rail click expands | Pass | Click on rail icon re-expands right panel |
| T8 - Chat streaming | Pass | Streaming response confirmed |
| T9 - Chat History view | Pass | Dropdown switches to sessions list; empty-state shown when no sessions |

**Signed off:** 2026-05-11
