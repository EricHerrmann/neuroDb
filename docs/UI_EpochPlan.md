# NeuroDb — UI Epoch Plan

**Status:** UI-2 complete — React workbench prototype signed off 2026-05-11
**Last updated:** 2026-05-11
**Epoch directory:** `src/neurodb/ui/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Own the UI shell, routing, pane layout, streaming rendering, and workbench state. Current implementation is Streamlit. Target is a FastAPI + React workbench shell — migration is incremental with Streamlit retained until parity.

**Active work:** None — UI-2 signed off. Next UI work is UI-2B layout redesign or UI-3 parity migration.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| Streamlit MVP | Streamlit shell — chat, research, knowledge library, sidebar | Complete | — | 2026-05-06 | — |
| UI-0 | Architecture decision record — FastAPI + React target confirmed; Streamlit retained during migration | Complete (ADR) | — | 2026-05-08 | — |
| UI-1 | FastAPI backend shell — app factory, 8 API routes, SSE chat PoC | Complete | 408 automated + 9 manual | 2026-05-11 | `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_ui1_api_shell.md` |
| UI-2 | React workbench prototype — Vite + React + React Router + TanStack Query; same two-column layout as Streamlit; all 7 panels functional; infrastructure migration only | Complete | 443 automated Python + 7 frontend + 11 manual | 2026-05-11 | `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_ui2_react_workbench.md` |
| UI-2B | Layout redesign — activity rail, resizable panes; deferred from UI-2 | Planned | — | — | — |
| UI-3 | Parity migration — Streamlit surfaces moved to React one at a time | Planned | — | — | — |
| UI-4 | Streamlit retirement decision | Planned | — | — | — |

Active test plan: none

---

## Open Backlog

| Log ID | Issue |
|--------|-------|
| LOG-013 | UI shell rearchitecture — deferred post-LT-3; addressed by UI-0 ADR and UI-1 plan |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-08 | FastAPI + React as target shell; Streamlit retained until parity | Workbench ergonomics (persistent panes, independent scroll, routing, streaming) require React; rewrite is incremental — Streamlit is not retired until replacement has parity. See `docs/superpowers/plans/2026-05-08-ui1-backend-api-shell.md`. |
| 2026-05-08 | UI does not own agent or session state | Session messages, tool results, and agent context live in the agent or Agent Core's session store — not in Streamlit session state or React component state |
| 2026-05-11 | Activity rail and resizable panes deferred from UI-2 to UI-2B | UI-2 is a clean infrastructure migration — same layout as Streamlit, all 7 panels working. Layout redesign is a separate concern and would conflate two orthogonal changes. |
| (deferred) | Provider selection UI for tier routing | Settings panel with three provider dropdowns (Economy, Standard, Premium) — deferred until FastAPI + React shell exists; current control is editing `neurodb_models.toml` `[routing]` section directly |

Historical options analysis and pros/cons: `docs/archive/UI_EpochPlan_historical.md`

---

## Technology Stack

| Layer | Current | Target | Phase |
|-------|---------|--------|-------|
| UI shell | Streamlit | React (Vite or framework) | UI-2 |
| Backend API | None (direct Python calls) | FastAPI | UI-1 |
| Agent streaming | Streamlit rerun | SSE or WebSocket | UI-1 |
| State management | `st.session_state` | React component + server state | UI-2 |
| SQL workspace | Streamlit textarea | React panel (Monaco deferred) | UI-3 |
