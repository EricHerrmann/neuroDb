# NeuroDb — Project Status

**Last updated:** 2026-05-04
**Active focus:** P7 — TBD
**Next phase:** P7 — TBD
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
| P5 — Learning Agent Enhancement | ✅ Signed off | 151 | 2026-05-04 |
| P6 — Learning Agent Features | ✅ Signed off | 162 | 2026-05-04 |

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
| `src/neurodb/chapter_registry.py` | Augustine 7th ed. chapter → title + topics lookup |
| `src/neurodb/discovery_tools.py` | Discovery mode tool implementations and DISCOVERY_TOOLS schema |
| `docs/superpowers/specs/2026-05-01-learning-agent-enhancement-design.md` | Design spec: learning-focused agent with mode toggle, chapter registry, discovery tools, suggestions UI |
| `docs/superpowers/plans/2026-05-01-learning-agent-enhancement.md` | P5 implementation plan |
| `docs/testsPlans/manualTestPlan_agent_p5.md` | Manual verification plan for P5 — Learning Agent Enhancement |
| `docs/superpowers/specs/2026-05-04-p6-learning-agent-features.md` | P6 signed-off scope: embedding dedup, agent streaming, UI redesign |
| `docs/testsPlans/manualTestPlan_agent_p6.md` | Manual verification plan for P6 — embedding dedup, streaming, split-workspace UI |
| `docs/testRuns/2026-05-04-p6-run1.md` | P6 manual test run log — F1/F2/F3 passed after final UI update |
| `docs/testRuns/README.md` | Test run log conventions: LOG: protocol, naming, fix-pass trigger |
| `docs/testRuns/_template.md` | Standard template for per-phase test run log files |
| `docs/testRuns/2026-05-04-p5-run1.md` | P5 manual test run log — all 8 tests passed; T4 chat-history-clear noted |

## Active Manual Test Plans

| Document | Phase | Status |
|---|---|---|
| None | — | — |

## Archived Test Plans

| Document | Phase | Outcome |
|---|---|---|
| `docs/testsPlans/manualTestPlan_agent_p5.md` | P5 — Learning Agent Enhancement | ✅ Signed off 2026-05-04 |
| `docs/testsPlans/manualTestPlan_agent_p6.md` | P6 — Learning Agent Features | ✅ Signed off 2026-05-04 |
| `docs/testsPlans/manualTestPlan_agent_p4.md` | P4 — Context Persistence | ✅ Signed off 2026-04-29 |
| `docs/testsPlans/manualTestPlan_agent_p1.md` | P1 — Study Tag Layer | ✅ Signed off 2026-04-27 |
| `docs/testsPlans/manualTestPlan_agent_p2.md` | P2 — Embedding Layer | ✅ Signed off 2026-04-27 |
| `docs/testsPlans/manualTestPlan_agent_p3.md` | P3 — AI Agent Interface | ✅ Signed off 2026-04-27 |
| `docs/testsPlans/manualTestPlan_phase2.md` | Phase 2 — MVP UI | ✅ Complete |
| `docs/testsPlans/manualTestPlan_phase3.md` | Phase 3 — Allen Brain | ✅ Complete |
| `docs/testsPlans/manualTestPlan_phase4.md` | Phase 4 — Query layer | ✅ Complete |
| `docs/testsPlans/manualTestPlan_phase5.md` | Phase 5 — DuckDB migration | ✅ Signed off 2026-04-13 |
