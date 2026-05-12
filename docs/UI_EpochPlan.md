# NeuroDb — UI Epoch Plan

**Status:** UI-3 implementation complete — manual verification pending
**Last updated:** 2026-05-12
**Epoch directory:** `src/neurodb/ui/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Active Work

UI-3 manual verification — 7 write operations wired to React; Streamlit banner added.
UI-5 draft design complete — 26 gaps identified across 8 panels (6 P1 data-integrity, 10 P2 core workflow, 10 P3 polish + enhancements). See `docs/superpowers/specs/2026-05-12-ui5-parity-completion-design.md`.

---

## Epoch Goal

Own the UI shell, routing, pane layout, streaming rendering, and workbench state. Current implementation is Streamlit. Target is a FastAPI + React workbench shell — migration is incremental with Streamlit retained until parity.

**Active work:** UI-3 manual verification — 7 write operations wired to React; Streamlit banner added.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| Streamlit MVP | Streamlit shell — chat, research, knowledge library, sidebar | Complete | — | 2026-05-06 | — |
| UI-0 | Architecture decision record — FastAPI + React target confirmed; Streamlit retained during migration | Complete (ADR) | — | 2026-05-08 | — |
| UI-1 | FastAPI backend shell — app factory, 8 API routes, SSE chat PoC | Complete | 408 automated + 9 manual | 2026-05-11 | `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_ui1_api_shell.md` |
| UI-2 | React workbench prototype — Vite + React + React Router + TanStack Query; same two-column layout as Streamlit; all 7 panels functional; infrastructure migration only | Complete | 443 automated Python + 7 frontend + 11 manual | 2026-05-11 | `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_ui2_react_workbench.md` |
| UI-2B | Layout redesign — activity rail (replaces sidebar + PanelNav), resizable + collapsible right panel, agent mode in chat header, chat history in Study Log | Complete | 19 frontend + 9 manual | 2026-05-11 | `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_ui2b_layout_redesign.md` |
| UI-3 | Parity migration — 7 write operations wired to React; Streamlit deprecation banner | Implementation complete; manual verification pending | 474 Python + 43 frontend + build | — | `docs/testsPlans/manualTestPlan_ui3_parity_migration.md` |
| UI-4 | Streamlit retirement decision | Planned | — | — | — |
| UI-5 P1 | Data integrity fixes — 6 gaps: study log embedding, KL ChromaDB indexing, ImportQueue status, promote provenance, suggest type gating, registry topics | Complete | 485 Python + 47 frontend + build | 2026-05-12 | — |
| UI-5 P2+ | Parity completion — 20 remaining gaps (P2 core workflow + P3 polish) | Planned | — | — | — |

Active test plan: `docs/testsPlans/manualTestPlan_ui3_parity_migration.md` (UI-3 manual verification still pending)

---

## Open Backlog

| Log ID | Issue |
|--------|-------|
| LOG-013 | UI shell rearchitecture — deferred post-LT-3; addressed by UI-0 ADR and UI-1 plan |

### UI-5 Backlog (Draft — See Spec for Full Detail)

Identified in 2026-05-12 Streamlit vs React comparison. Organized by capability, then priority.

#### Chat
| Priority | Feature | Notes |
|---|---|---|
| P2 | Tool activity log — collapsible pane per turn | SSE events already emitted; frontend only |
| P2 | Clear + auto-summarize | Requires `POST /api/sessions/{id}/end` |
| P3 | Prior context banner | Shows `active_prior_topic` from preferences |

#### Study Log
| Priority | Feature | Notes |
|---|---|---|
| P1 | Vector embedding on create | Route must call `embed_note` after `tag_dataset` |
| P2 | Delete tag | `DELETE /api/study-log/{id}` + `remove_note` + Remove button per row |
| P2 | Filter by concept + source | Client-side filter on loaded list |
| P3 | Row-select → prefill form | `PATCH /api/study-log/{id}` for edit path |
| P3 | Source list alignment | Add allen_brain, neurovault, dandi to React select |

#### Datasets
| Priority | Feature | Notes |
|---|---|---|
| P2 | Modality filter | Add `modality` param to `GET /api/datasets`; existing helper already supports it |
| P2 | Rich metadata in results | Show title, modality, n_subjects (data likely already in API response) |
| P3 | Inline tag from result row | Mini form pre-filled with source/source_id; calls `POST /api/study-log` |
| Enhancement | Modality filter chips (multi-select) | Exceeds Streamlit single-select |

#### Suggestions
| Priority | Feature | Notes |
|---|---|---|
| P1 | ImportQueue.status update on import completion | Background thread must set `status='imported'` on success |
| P1 | Promote gating by suggestion_type | Show Promote only when `suggestion_type === 'learning_source'` |
| P1 | `added_by` on promote → "user" | Route currently hardcodes "suggestion"; change to "user" |

#### Registry
| Priority | Feature | Notes |
|---|---|---|
| P1 | Topics field in add form → content_json | Comma-separated topics serialized to `{"topics": [...]}` |
| P1 | Remove `added_by` from add form; hardcode "user" in route | Current free-text input produces inconsistent provenance |
| P3 | Content expansion in item cards | chapters for books, topics for others; requires `content_json` in API response |

#### Research
| Priority | Feature | Notes |
|---|---|---|
| P2 | Status filter chips for hypotheses + questions | Server-side filter param on both list routes |
| P2 | Hypothesis detail expansion | mechanism, evidence, predictions, confounds, limitations — inline toggle per card |
| P2 | Accept revisions / Dismiss review | `POST /api/research/reviews/{id}/accept` + dismiss; drives hypothesis lifecycle |
| Enhancement | Hypothesis slide-over drawer (later pass) | Full-panel drawer for detailed reading + review history |

#### Knowledge Library
| Priority | Feature | Notes |
|---|---|---|
| P1 | ChromaDB indexing on approve | Route must call `knowledge_store.add_summary` after status flip |
| P2 | LLM summary generation on approve | Background task; same pattern as import/review |
| P2 | Near-duplicate detection before approve | `GET /api/knowledge-library/{id}/duplicates`; warn if distance < threshold |
| P3 | DOI as clickable link | `https://doi.org/{doi}` if starts with `10.` |

#### SQL
| Priority | Feature | Notes |
|---|---|---|
| P3 | Table catalog hint + update default query | Cosmetic; no backend change |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-08 | FastAPI + React as target shell; Streamlit retained until parity | Workbench ergonomics (persistent panes, independent scroll, routing, streaming) require React; rewrite is incremental — Streamlit is not retired until replacement has parity. See `docs/superpowers/plans/2026-05-08-ui1-backend-api-shell.md`. |
| 2026-05-08 | UI does not own agent or session state | Session messages, tool results, and agent context live in the agent or Agent Core's session store — not in Streamlit session state or React component state |
| 2026-05-11 | Activity rail and resizable panes deferred from UI-2 to UI-2B | UI-2 is a clean infrastructure migration — same layout as Streamlit, all 7 panels working. Layout redesign is a separate concern and would conflate two orthogonal changes. |
| 2026-05-11 | Activity rail replaces both Sidebar and PanelNav | Sidebar held only agent mode (→ chat header) and session history (→ Study Log panel already covers this). Consolidating nav into a single 40px rail maximises horizontal space for chat and panel content. |
| 2026-05-11 | Right panel collapsible to zero via react-resizable-panels | Full-width chat mode useful for long reading sessions; clicking any rail icon re-expands. Constrained-only resize was simpler but the collapse feature is one prop (`collapsible`) with no extra complexity. |
| (deferred) | Provider selection UI for tier routing | Settings panel with three provider dropdowns (Economy, Standard, Premium) — deferred until FastAPI + React shell exists; current control is editing `neurodb_models.toml` `[routing]` section directly |

Historical options analysis and pros/cons: `docs/archive/UI_EpochPlan_historical.md`

---

## Key References

| Document | Purpose |
|---|---|
| `docs/superpowers/specs/2026-05-11-ui2-react-workbench-design.md` | UI-2 design spec |
| `docs/superpowers/specs/2026-05-11-ui2b-layout-redesign.md` | UI-2B design spec |
| `docs/superpowers/specs/2026-05-11-ui3-parity-migration-design.md` | UI-3 design spec — 7 write operations, background task system |
| `docs/superpowers/specs/2026-05-12-ui5-parity-completion-design.md` | UI-5 draft design — 26 gaps, P1/P2/P3/Enhancement by capability |
| `docs/superpowers/specs/2026-05-12-ui5-p1-data-integrity-design.md` | UI-5 P1 design spec — 6 data-integrity fixes, warning propagation pattern |
| `docs/superpowers/plans/2026-05-12-ui5-p1-data-integrity.md` | UI-5 P1 implementation plan — 6 tasks complete |
| `docs/superpowers/plans/2026-05-11-ui2-react-workbench.md` | UI-2 implementation plan (complete) |
| `docs/superpowers/plans/2026-05-11-ui2b-layout-redesign.md` | UI-2B implementation plan (complete) |
| `docs/superpowers/plans/2026-05-11-ui3-parity-migration.md` | UI-3 implementation plan (15 tasks) |
| `docs/testsPlans/manualTestPlan_ui3_parity_migration.md` | UI-3 active manual test plan |

---

## Technology Stack

| Layer | Current | Target | Phase |
|-------|---------|--------|-------|
| UI shell | Streamlit | React (Vite or framework) | UI-2 |
| Backend API | None (direct Python calls) | FastAPI | UI-1 |
| Agent streaming | Streamlit rerun | SSE or WebSocket | UI-1 |
| State management | `st.session_state` | React component + server state | UI-2 |
| SQL workspace | Streamlit textarea | React panel (Monaco deferred) | UI-3 |
