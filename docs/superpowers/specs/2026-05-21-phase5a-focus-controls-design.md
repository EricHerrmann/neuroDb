# Phase 5a — Focus Controls and Agent In-Progress Feedback

**Date:** 2026-05-21
**Status:** Design approved — ready for implementation planning
**Epoch:** UI
**Parent spec:** `docs/superpowers/specs/2026-05-18-learning-research-memory-refocus-design.md`

---

## Goal

Give the user visible, interactive control over the context mode that governs agent behavior, compact the chat header so model tier information is accessible without consuming permanent space, and eliminate the two silent dead zones between message submit and first visible agent output.

Phase 5a is frontend-only except for the tooltip component. All required API endpoints (`GET /api/preferences`, `PUT /api/preferences/context-mode`, `GET /api/model-info`) already exist from Phase 4.

---

## Non-Goals

- Model tier selection (read-only in P5a; interactive selection is a later pass)
- Models dropdown tooltip (deferred — needs a robust tooltip system; noted in UI epoch backlog)
- LOG-060 chat hang investigation (deferred)
- Evidence Lens, Dataset Honesty, retract lifecycle (P5b)
- Provider selection UI

---

## Architecture

### 1. Chat Header Redesign

Replace the current model tier inline text display with three compact dropdowns, ordered left-to-right after the Clear button:

**Models → Agent Mode → Context Mode**

#### Models Dropdown

- Label: `Models`
- Read-only. Opens to show the three tier mappings from `GET /api/model-info`:
  ```
  Low  → {tiers.low.model}
  Mid  → {tiers.mid.model}
  High → {tiers.high.model}
  ```
- No selection, no write path.
- Tooltip system deferred; backlog note added to UI epoch.

#### Agent Mode Dropdown

Existing `<select>` behavior unchanged.

#### Context Mode Dropdown

- Only rendered when `agentMode` is `neuro_tutor` or `neuro_research`. Hidden for `local_db` and `external_db` — context modes do not apply to those agents.
- Reads `context_mode` from `GET /api/preferences` on component mount.
- Writes via `PUT /api/preferences/context-mode` on change.
- Visually distinguished: blue border tint when active to signal it affects agent behavior.
- Hover tooltip on each option (see Tooltip section below).

**Options:**

| Value | Label | Tooltip |
|---|---|---|
| `general` | General | Model knowledge only. Use before you have local data on a topic. |
| `contextual` | Contextual | NeuroDb context prepended. Use when working with ingested data. *(default)* |
| `grounded` | Grounded | Local evidence only. Names missing sources instead of filling gaps. Use for hypothesis work. |

#### Tooltip Component

A small `Tooltip.tsx` component wrapping any element with hover-triggered popover text. Used by the context mode dropdown options. Implementation: CSS-positioned `<span>` shown on `onMouseEnter` / hidden on `onMouseLeave`. No third-party dependency.

---

### 2. Agent In-Progress Feedback

Two dead zones are eliminated by surfacing state already tracked in `useChat`.

#### State Machine

| State | Trigger | Bubble content |
|---|---|---|
| `idle` | No active turn | Empty |
| `thinking` | Message submitted, no SSE event yet | `Thinking ···` (animated) |
| `tool` | `tool_start` SSE event received | `▸ {tool_name} ···` (animated) |
| `streaming` | `text_delta` received | Streaming text |
| `complete` | Stream closed | Final text + collapsed `<details>` tool trace |

#### Dead Zone 1 — Submit → First SSE Event

As soon as the user submits, the assistant bubble renders with `Thinking ···`. Three dots animate in sequence via CSS keyframe (`opacity` stagger). Clears on the first of `text_delta`, `tool_start`, or `context_summary`.

#### Dead Zone 2 — Tool Executing (tool_start → tool_result)

When `tool_start` arrives, the bubble updates to `▸ {tool_name} ···`. If multiple tools run in sequence, the name updates to the current tool on each `tool_start`. Clears to streaming text on first `text_delta`.

The existing collapsed `<details>` tool activity pane is unchanged — available after response completion for users who want the full tool trace.

#### useChat Changes

Expose two new values from `useChat`:
- `thinkingState: 'idle' | 'thinking' | 'tool' | 'streaming'`
- `activeTool: string | null` — populated from the most recent `tool_start` event name

---

## API Surface

No new endpoints. All reads and writes use existing routes:

| Route | Use |
|---|---|
| `GET /api/preferences` | Read `context_mode` and `agent_mode` on mount |
| `PUT /api/preferences/context-mode` | Persist context mode on dropdown change |
| `GET /api/model-info` | Read tier → model mapping for Models dropdown |

---

## Frontend Files

| File | Change |
|---|---|
| `frontend/src/components/ChatPanel.tsx` | Header redesign — three dropdowns, context mode conditional render; render `ThinkingBubble` inline after messages map when `thinkingState !== 'idle'` |
| `frontend/src/hooks/useChat.ts` | Add `thinkingState` and `activeTool` to hook return |
| `frontend/src/components/Tooltip.tsx` | New — hover tooltip component used by context mode options |
| `frontend/src/components/ThinkingBubble.tsx` | New — renders `Thinking ···` (DZ1) and `▸ {tool_name} ···` (DZ2) during in-progress states; not reused by MessageBubble |

---

## Testing

### Automated (frontend unit)

| Test | Coverage |
|---|---|
| Context mode dropdown renders for `neuro_tutor` and `neuro_research` | Visibility rule |
| Context mode dropdown absent for `local_db` and `external_db` | Visibility rule |
| Selecting a mode calls `PUT /api/preferences/context-mode` with correct value | Write path |
| Models dropdown renders Low/Mid/High rows from `GET /api/model-info` | Read-only display |
| Tooltip text correct for each of the three context modes | Content accuracy |
| `useChat` exposes `thinkingState` and `activeTool` with correct shape | State shape |
| Bubble shows `Thinking ···` when `thinkingState === 'thinking'` | DZ1 rendering |
| Bubble shows tool name when `thinkingState === 'tool'` | DZ2 rendering |
| Bubble transitions to text on `text_delta` | State transition |

### Manual

| Step | Pass criterion |
|---|---|
| Switch context mode → send same question in each | Response visibly differs across General / Contextual / Grounded |
| Hover each option in context mode dropdown | Correct tooltip appears for each mode |
| Switch to Local DB or External DB agent mode | Context mode dropdown disappears from header |
| Submit a message that triggers tool calls | `Thinking ···` → tool name → text flows with no blank gap |
| Open `<details>` after response completes | Full tool trace visible |
| Open Models dropdown | All three tier → model mappings shown; nothing is selectable |

---

## Open Items Addressed

| Log ID | Resolution |
|---|---|
| LOG-006 | Models dropdown surfaces active tier → model mapping; interactive selection deferred |

## Deferred

| Item | Deferred to |
|---|---|
| LOG-060 chat hang | Investigation — no phase assigned |
| Models dropdown tooltip | UI epoch backlog — needs robust tooltip system |
| Model tier selection (interactive) | Later UI pass |
