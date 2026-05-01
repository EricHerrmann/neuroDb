# NeuroDb — Project Status

**Last updated:** 2026-05-01
**Active focus:** Learning Agent Enhancement — mode-aware agent, chapter registry, discovery tools, suggestions UI
**Next phase:** Learning Agent Enhancement → Deferred: Entity resolution (Phase 7)
**Goal alignment:** Building the study/learning agent layer that grounds neuroscience exploration in real ingested dataset IDs, accumulating cross-session context as the user's knowledge deepens.

---

## DB Epoch Phases

| Phase | Status | Tests | Sign-off |
|---|---|---|---|
| 0 — Scaffolding | ✅ Complete | — | — |
| 1 — OpenNeuro connector | ✅ Complete | — | — |
| 2 — MVP UI | ✅ Complete | — | — |
| 3 — Allen Brain + views | ✅ Complete | — | — |
| 4 — Query & analysis layer | ✅ Complete | — | — |
| 5 — DuckDB migration | ✅ Complete | 35 | 2026-04-13 |
| 6 — NeuroVault + DANDI | ✅ Complete | 74 | — |
| 7 — Entity resolution | ⏳ Decision pending | — | — |
| 8 — Hypothesis layer | ⏳ Not started | — | — |

## Neuro Learning Agent Phases

| Phase | Status | Tests | Sign-off |
|---|---|---|---|
| P1 — Study Tag Layer | ✅ Signed off | 84 | 2026-04-27 |
| P2 — Embedding Layer (ChromaDB + SPECTER2) | ✅ Signed off | 84 | 2026-04-27 |
| P3 — AI Agent Interface | ✅ Signed off | 101 | 2026-04-27 |
| P4 — Context Persistence | ✅ Signed off | 127 | 2026-04-29 |
| P5 — Learning Agent Enhancement | ⏳ In progress | — | — |

---

## Source Documents

| Document | Purpose |
|---|---|
| `docs/ClaudeDbEpochPlan.md` | Master plan: all phases, decisions log, architecture, tech stack |
| `docs/superpowers/specs/2026-04-24-neuro-learning-agent-design.md` | Agent layer design spec: P1–P4 component design, data flow, testing strategy |
| `docs/superpowers/plans/2026-04-24-agent-p1-study-tag-layer.md` | P1 implementation plan |
| `NeuroDbGoals.md` | Top-level project goals and learning model |
| `CLAUDE.md` | Coding standards, process rules, environment setup for agents |
| `docs/neuroscience/chap12NeuroDb.md` | Ch 12 (Central Visual Pathways) — how to use NeuroDb to reinforce reading |
| `docs/superpowers/specs/2026-05-01-learning-agent-enhancement-design.md` | Design spec: learning-focused agent with mode toggle, chapter registry, discovery tools, suggestions UI |
| `docs/superpowers/plans/2026-05-01-learning-agent-enhancement.md` | P5 implementation plan |

## Active Manual Test Plans

| Document | Phase | Status |
|---|---|---|
| _(none)_ | — | — |

## Archived Test Plans

| Document | Phase | Outcome |
|---|---|---|
| `docs/testsPlans/manualTestPlan_agent_p4.md` | P4 — Context Persistence | ✅ Signed off 2026-04-29 |
| `docs/testsPlans/manualTestPlan_agent_p1.md` | P1 — Study Tag Layer | ✅ Signed off 2026-04-27 |
| `docs/testsPlans/manualTestPlan_agent_p2.md` | P2 — Embedding Layer | ✅ Signed off 2026-04-27 |
| `docs/testsPlans/manualTestPlan_agent_p3.md` | P3 — AI Agent Interface | ✅ Signed off 2026-04-27 |
| `docs/testsPlans/manualTestPlan_phase2.md` | Phase 2 — MVP UI | ✅ Complete |
| `docs/testsPlans/manualTestPlan_phase3.md` | Phase 3 — Allen Brain | ✅ Complete |
| `docs/testsPlans/manualTestPlan_phase4.md` | Phase 4 — Query layer | ✅ Complete |
| `docs/testsPlans/manualTestPlan_phase5.md` | Phase 5 — DuckDB migration | ✅ Signed off 2026-04-13 |
