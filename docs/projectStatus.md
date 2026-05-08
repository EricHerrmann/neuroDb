# NeuroDb — Project Status

**Last updated:** 2026-05-08
**Active focus:** Config Control Phase 4 complete — 382 automated tests; LOG-044 resolved via submit_critique tool-use
**Next:** Manual evals for Phase 4 (T1–T6 in manualTestPlan_config_phase4.md)
**Goal alignment:** Two co-equal goals in a feedback loop — accumulate neuroscience understanding grounded in real data (Goal 1), and conduct structured neuroscience investigations using existing public datasets and good scientific method (Goal 2). See `NeuroDbGoals.md`.

---

## Epoch Status

| Epoch | Maturity | Next |
|---|---|---|
| DB | MVP complete (phases 0–6) | Entity resolution (7), research storage schema (8) |
| Agent Core | Stable | Config Control Phases 1–4 complete; manual evals pending for Phase 4 OpenAI parity |
| Tutor | MVP complete (LT-1/2/3) | Open backlog: LOG-001, LOG-006, LOG-030 |
| Research | Scaffolded (LT-3); hypothesis review with structured tool-use output | Research run management, research question actions (LOG-037) |
| UI | Streamlit MVP; migration designed | UI-0 architecture decision, FastAPI + React vertical slice |
| Config Control | Phase 4 complete — 382 automated tests; LOG-044 resolved; manual evals pending | Phase 4 manual evals (T1–T6) |

---

## Tech Debt (complete)

| Sprint | Focus | Status |
|--------|-------|--------|
| TD-1 | Schema migration framework, connector fetch_by_id/search_by_keyword on all sources, explicit connector registry, StudyNote unique constraint, dependency pinning | Complete — 186 tests |
| TD-2 | Unit tests: embedder, enrichment, provenance; clear button behavioral tests | Complete — 204 tests |
| TD-3 | Dead code removal, model name env var, api_messages rollback on exception, QualityEvent compound index, chapter context guard, pytest-cov | Complete — 210 tests |

---

## Open Issues

See `docs/testLog.md`. Current open items: LOG-001 (textbook dropdown ambiguity — deferred post-LT-3), LOG-006 (model visibility — deferred post-LT-3), LOG-013 (UI shell rearchitecture — deferred post-LT-3), LOG-030 (LT-3 header/title sizing), LOG-037 (research-question actions), LOG-040 (Config Phase 1 local DB no-results wait behavior), LOG-041 (session summary visibility). LOG-044 resolved in Phase 4 via submit_critique tool-use.

---

## Completed

| Phase | What | Date |
|-------|------|------|
| LT-1 | BaseAgent architecture, NeuroTutorAgent, auto-session, Knowledge Library storage + UI | 2026-05-05 |
| LT-2 | Live literature search, Previous Topics, session memory, Knowledge Library polish | 2026-05-06 |
| LT-3 | Research agent scaffolding, knowledge growth metrics, hypothesis tools | 2026-05-06 |
| Config Control Phase 1 | Per-agent model env vars and summary model routing — 332 tests plus 5 manual evals passed | 2026-05-07 |
| Config Control Phase 2 | Model-call telemetry for agent loops and summary calls — 344 tests plus 7 manual evals passed | 2026-05-08 |
| Config Control Phase 3 | Research Synthesis Split: Sonnet draft loop plus premium hypothesis review — 350 tests plus 4 manual evals passed | 2026-05-08 |
| Config Control Phase 4 | ModelClient abstraction, AnthropicModelClient, OpenAIModelClient, TaskRouter, config-driven model table, BaseAgent refactor, LOG-044 fix — 382 automated tests | 2026-05-08 |
| Pre-LT-2 | Sidebar migration | 2026-05-05 |
| P1–P4 | Learning agent MVP: study tags, embeddings, agent interface, context persistence | 2026-04-29 |
| P5 | Learning Agent Enhancement: mode toggle, chapter registry, discovery tools, suggestions UI | 2026-05-04 |
| P6 | Learning Agent Features: embedding dedup, agent streaming, split-workspace UI | 2026-05-04 |
| DB Epochs 0–6 | Data platform: ingest, normalize, DuckDB, NeuroVault/DANDI connectors | 2026-04-13 |

**Deferred:** DB Epochs 7 (entity resolution) and 8 (hypothesis layer) — decision pending. See `docs/ClaudeDbEpochPlan.md`.

---

## Key References

| Document | Purpose |
|----------|---------|
| `NeuroDbGoals.md` | Top-level project goals and feedback loop |
| `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md` | Epoch architecture spec — six epochs, interface contracts, coupling rules, goal-to-epoch mapping |
| `docs/superpowers/plans/2026-05-07-epoch-framework-adoption.md` | Epoch framework adoption plan — doc updates, directory stubs, module docstrings |
| `CLAUDE.md` | Engineering rules, process, environment |
| `docs/ClaudeLearnEpochPlan.md` | Learning Epoch architecture reference — Neuro-Tutor and agent pattern context |
| `docs/ClaudeDbEpochPlan.md` | DB epoch plan and architecture decisions |
| `docs/uiEpoch.md` | UI epoch plan — Streamlit constraints, FastAPI/React workbench migration path |
| `docs/codexTaskAnalysis.md` | Codex task-based cost analysis, model-routing recommendations, and provider-agnostic architecture notes |
| `docs/claudeTaskAnalysis.md` | Task taxonomy, model tier assignments, multi-provider architecture design, and phased implementation plan |
| `docs/superpowers/plans/claudeTaskArch.md` | Design plan — capability tiers, per-agent env vars, synthesis split, provider abstraction, phased implementation |
| `docs/superpowers/plans/2026-05-07-model-routing-impl.md` | Phased implementation plan — task checklists for Phase 1–4, file map, eval gates, stop criteria |
| `docs/superpowers/plans/2026-05-07-config-phase2-cost-telemetry.md` | Config Phase 2 signed-off design — ModelCallLog schema, telemetry helper, instrumentation boundaries, tests |
| `docs/testLog.md` | Running issue log — open and resolved items across all phases |
| `docs/testsPlans/manualTestPlan_config_phase1.md` | Config Phase 1 signed-off manual test plan — per-agent model env var evals |
| `docs/testsPlans/manualTestPlan_config_phase2.md` | Config Phase 2 signed-off manual test plan — model-call telemetry evals |
| `docs/testsPlans/manualTestPlan_config_phase3.md` | Config Phase 3 signed-off manual test plan — research synthesis split and premium hypothesis review evals |
| `docs/testsPlans/manualTestPlan_config_phase4.md` | Config Phase 4 active manual test plan — ModelClient parity, TaskRouter wiring, hypothesis review tool-use, OpenAI provider evals |
