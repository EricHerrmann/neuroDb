# Pre-LT-2: Chat Layout Hardening — Design Spec

**Date:** 2026-05-05
**Status:** Approved — ready for implementation planning
**Dependency for:** LT-2 (sidebar structure must exist before Previous Topics and Connections sections are added)
**Sequencing:** Fully implemented and tested before any LT-2 code is written.

---

## Goal

Fix the core usability failure of the current chat layout: as conversations grow, the text input scrolls off the bottom of the screen and the workspace pane goes out of view. Both columns should behave like independent scroll containers — the page itself never scrolls.

---

## Problem Statement

The current layout renders as a single scrolling page. As the chat transcript grows:
- The text input slides below the viewport — users must scroll down to reach it
- Scrolling down to the input takes the right workspace pane with it, making both panes unavailable simultaneously
- The mode toggle (at the top of the left column) becomes unreachable without scrolling back up

The fix is a VSCode-style fixed-pane layout: each column occupies full viewport height and scrolls internally. The page itself never scrolls.

---

## Design

### 1. Fixed-Height Column Layout

Both columns (`col_chat` and `col_workspace` in `app.py`) become fixed-height scroll containers. Implemented via CSS injection in `_inject_ui_styles()`:

- Outer column wrappers: `height: calc(100vh - Npx)`, `overflow: hidden` (where N accounts for the Streamlit toolbar)
- Transcript container: `flex: 1`, `overflow-y: auto` — scrolls independently within the left pane
- Right workspace container: `overflow-y: auto` — scrolls independently
- The page-level scroll is suppressed: `body { overflow: hidden }`

The exact pixel offset N is determined empirically against the current Streamlit toolbar height (approximately 60px). If Streamlit's toolbar height changes in a future version, N is the only value to update.

### 2. Input Pinned to Bottom

The left pane uses a flex column layout:
- Row 1: transcript container (`flex: 1`, scrolls)
- Row 2: text input + Send/Clear buttons (`flex-shrink: 0`, pinned)

The input is always visible regardless of transcript length. No user action required to reach it.

### 3. Transcript Auto-Scroll

After each agent response, the transcript scrolls to the newest message automatically. Implemented via a JavaScript scroll-to-bottom call injected as a Streamlit component or `st.markdown` HTML snippet. The scroll fires after `st.rerun()` settles, targeting the transcript container's scrollable div.

The user can still scroll up manually to review prior messages — auto-scroll only triggers after a new agent response is appended.

### 4. Mode Toggle and Chapter Context → Streamlit Sidebar

The mode radio (`Local DB / External DB / Neuro-Tutor`) and chapter context controls (textbook selector, chapter input, active context display) move from the main chat panel into Streamlit's native left sidebar (`st.sidebar`).

**Sidebar behavior:** Streamlit's native sidebar is collapsible. When collapsed, both columns expand proportionally to fill the full viewport width. When expanded, columns fill the remaining width (~75–80%). The fixed-height CSS is column-relative, so sidebar state does not affect the fixed-height or scroll behavior.

**Sidebar width:** Fixed at Streamlit's default (~300px). Not user-resizable via drag — accepted limitation for this project stage.

### 5. Sidebar as Extensible Configuration Panel

The sidebar is structured with named sections from day one, so future items (model selection, API key status, user preferences) slot in without restructuring. LT-2 adds Previous Topics and Connections sections into this same structure.

**Pre-LT-2 sidebar structure:**

```
▼ Agent
   Mode: [Local DB] [External DB] [Neuro-Tutor]

▼ Context  (only shown when mode ≠ neuro_tutor)
   Textbook: [dropdown]
   Chapter: [text input]
   Active: Ch12 — Central Visual Pathways
   [Clear chapter context]

— (LT-2 adds: Previous Topics, Connections) —

DB: neurodb.duckdb
Session: active / none
```

Each section is a collapsible `st.expander` or a clearly separated `st.markdown` block with a divider. The Agent and Context sections are expanded by default. Reserved section slots are not rendered — they appear when LT-2 adds them.

### 6. chat.py Cleanup

With mode toggle and chapter context removed from `chat.py`, `_render_mode_and_chapter()` is deleted. `render_panel()` is simplified: it initializes the agent, renders the chat, and nothing else. The mode initialization (`_init_agent`) still reads `st.session_state["agent_mode"]` — the sidebar writes to that key, so the agent wiring is unchanged.

---

## What Does Not Change

- Agent instantiation logic (`_init_agent`) — unchanged
- Auto-session behavior (start on first message, summarize on Clear) — unchanged
- `api_messages` and `chat_history` session state — unchanged
- Workspace right pane tabs and content — unchanged
- All existing tests — must continue to pass

---

## Testing

- **Structural:** `chat.py` no longer contains `st.radio` or chapter context widgets. Sidebar module contains them.
- **Layout:** manual verification that input is visible without scrolling at 10, 20, and 30 messages.
- **Auto-scroll:** manual verification that newest message is in view after each agent response.
- **Sidebar collapse:** manual verification that both columns fill available width when sidebar is toggled.
- **Existing test suite:** all 255 tests pass after the refactor.

---

## Out of Scope

- Drag-to-resize sidebar or column split
- Smooth animated sidebar transition
- Any LT-2 sidebar sections (Previous Topics, Connections) — those are LT-2 scope
