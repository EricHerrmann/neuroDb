# Phase 5a Implementation Spec — Focus Controls and Agent In-Progress Feedback

**Date:** 2026-05-21
**Status:** Implementation ready
**Design source:** `docs/superpowers/specs/2026-05-21-phase5a-focus-controls-design.md`
**Manual test plan:** `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase5a_focus_controls.md`
**Epoch:** UI

---

## Scope

Implement Phase 5a exactly as a frontend-focused increment:

- Replace permanent model-tier header text with a compact read-only Models dropdown.
- Add a Context Mode dropdown for Neuro Tutor and Neuro Research only.
- Persist context mode through the existing preferences API.
- Add lightweight tooltip support for context mode descriptions.
- Surface in-progress assistant state so the chat pane is never blank between submit, tool execution, and first streamed text.

No backend endpoint changes are required. Existing endpoints are sufficient:

- `GET /api/preferences`
- `PUT /api/preferences/context-mode`
- `GET /api/model-info`
- `POST /api/chat/turn`

---

## Phase 1 — Header Focus Controls

Files:

- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/components/Tooltip.tsx`
- `frontend/src/components/ChatPanel.test.tsx`

Implementation:

1. Fetch preferences in `ChatPanel` using `api.getPreferences`.
2. Replace inline `Low/Mid/High` model labels with a disabled read-only `<select>` labeled `Models`.
3. Keep the existing Agent Mode select and mutation behavior.
4. Add a Context Mode select only for `neuro_tutor` and `neuro_research`.
5. Use `api.setContextMode` for persistence and keep the React Query preferences cache in sync.
6. Wrap the Context Mode control in `Tooltip` so the selected mode description appears on hover.

Exit criteria:

- Models dropdown shows Low/Mid/High mappings and cannot change state.
- Context Mode appears only for Neuro agents.
- Context Mode PUT is issued with the selected mode.
- Tooltip text matches the manual plan.

---

## Phase 2 — In-Progress Chat Feedback

Files:

- `frontend/src/hooks/useChat.ts`
- `frontend/src/hooks/useChat.test.ts`
- `frontend/src/components/ThinkingBubble.tsx`
- `frontend/src/components/ChatPanel.tsx`

Implementation:

1. Add `thinkingState: 'idle' | 'thinking' | 'tool' | 'streaming'` to `useChat`.
2. Add `activeTool: string | null` to `useChat`.
3. Set state to `thinking` immediately after submit.
4. Clear the first dead zone on the first SSE event that means the backend is active: `context_summary`, `tool_start`, `text_delta`, `done`, or `error`.
5. Set state to `tool` and update `activeTool` on every `tool_start`.
6. Set state to `streaming` on `text_delta`.
7. Reset state to `idle` on `done`, stream close, error, abort, or clear.
8. Render `ThinkingBubble` in the assistant stream area when `thinkingState` is `thinking` or `tool`.

Exit criteria:

- Submit immediately shows `Thinking ...`.
- Tool execution shows the active tool name.
- First streamed text replaces in-progress feedback.
- Completed tool traces remain in the existing collapsed details pane.

---

## Phase 3 — Verification and Status Sync

Files:

- `frontend/src/components/ChatPanel.test.tsx`
- `frontend/src/hooks/useChat.test.ts`
- `frontend/src/components/ThinkingBubble.test.tsx`
- `docs/projectStatus.md`

Implementation:

1. Add frontend unit coverage for header visibility, persistence, tooltip text, model dropdown rows, and in-progress state transitions.
2. Run focused frontend tests, then full frontend build.
3. Run focused Python tests only if backend types or API contracts are touched. P5a should not require backend code changes.
4. Update `docs/projectStatus.md` because this implementation spec is a new source document and P5a implementation state changes.

Exit criteria:

- `cd frontend && npm test -- ChatPanel.test.tsx useChat.test.ts ThinkingBubble.test.tsx`
- `cd frontend && npm run build`
- Project status references this implementation spec and P5a implementation state.
