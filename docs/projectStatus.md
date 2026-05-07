# NeuroDb — Project Status

**Last updated:** 2026-05-07
**Active focus:** LT-3 complete — signed off 2026-05-06
**Next:** Config Control Phase 1 (per-agent model env vars) — see `docs/superpowers/plans/2026-05-07-model-routing-impl.md`
**Goal alignment:** Two co-equal goals in a feedback loop — accumulate neuroscience understanding grounded in real data (Goal 1), and conduct structured neuroscience investigations using existing public datasets and good scientific method (Goal 2). See `NeuroDbGoals.md`.

---

## Epoch Status

| Epoch | Maturity | Next |
|---|---|---|
| DB | MVP complete (phases 0–6) | Entity resolution (7), research storage schema (8) |
| Agent Core | Stable | Config Control Phases 1–4: env-var wiring (1), BaseAgent instrumentation (2), ModelClient refactor (4) |
| Tutor | MVP complete (LT-1/2/3) | Open backlog: LOG-001, LOG-006, LOG-014, LOG-030 |
| Research | Scaffolded (LT-3) | Hypothesis review, research run management, research question actions (LOG-037) |
| UI | Streamlit MVP; migration designed | UI-0 architecture decision, FastAPI + React vertical slice |
| Config Control | Phase 1 in progress (Tasks 1.1–1.3 complete) | Phase 2: BaseAgent instrumentation |

---

## Tech Debt (complete)

| Sprint | Focus | Status |
|--------|-------|--------|
| TD-1 | Schema migration framework, connector fetch_by_id/search_by_keyword on all sources, explicit connector registry, StudyNote unique constraint, dependency pinning | Complete — 186 tests |
| TD-2 | Unit tests: embedder, enrichment, provenance; clear button behavioral tests | Complete — 204 tests |
| TD-3 | Dead code removal, model name env var, api_messages rollback on exception, QualityEvent compound index, chapter context guard, pytest-cov | Complete — 210 tests |

---

## Open Issues

See `docs/testLog.md`. Current open items: LOG-001 (textbook dropdown ambiguity — deferred post-LT-3), LOG-006 (model visibility — deferred post-LT-3), LOG-013 (UI shell rearchitecture — deferred post-LT-3), LOG-014 (Semantic Scholar API key policy — arch doc update), LOG-030 (LT-3 header/title sizing), LOG-037 (research-question actions).

---

## Completed

| Phase | What | Date |
|-------|------|------|
| LT-1 | BaseAgent architecture, NeuroTutorAgent, auto-session, Knowledge Library storage + UI | 2026-05-05 |
| LT-2 | Live literature search, Previous Topics, session memory, Knowledge Library polish | 2026-05-06 |
| LT-3 | Research agent scaffolding, knowledge growth metrics, hypothesis tools | 2026-05-06 |
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
| `docs/ClaudeLearnEpochPlan.md` | Learning Epoch plan — Neuro-Tutor, agent architecture pattern, phased roadmap |
| `docs/ClaudeDbEpochPlan.md` | DB epoch plan and architecture decisions |
| `docs/uiEpoch.md` | UI epoch plan — Streamlit constraints, FastAPI/React workbench migration path |
| `docs/codexTaskAnalysis.md` | Codex task-based cost analysis, model-routing recommendations, and provider-agnostic architecture notes |
| `docs/claudeTaskAnalysis.md` | Task taxonomy, model tier assignments, multi-provider architecture design, and phased implementation plan |
| `docs/superpowers/plans/claudeTaskArch.md` | Design plan — capability tiers, per-agent env vars, synthesis split, provider abstraction, phased implementation |
| `docs/superpowers/plans/2026-05-07-model-routing-impl.md` | Phased implementation plan — task checklists for Phase 1–4, file map, eval gates, stop criteria |
| `docs/testLog.md` | Running issue log — open and resolved items across all phases |
| `docs/superpowers/specs/2026-05-05-neuro-tutor-epoch-design.md` | LT-1 design spec |
| `docs/superpowers/plans/2026-05-05-lt1-neuro-tutor-foundation.md` | LT-1 implementation plan |
| `docs/superpowers/specs/2026-05-05-pre-lt2-chat-layout-hardening.md` | Pre-LT-2 design spec — sidebar migration retained, fixed-pane layout deferred |
| `docs/superpowers/plans/2026-05-05-pre-lt2-chat-layout-hardening.md` | Pre-LT-2 implementation plan — sidebar migration complete, fixed-pane layout failed/deferred |
| `docs/superpowers/specs/2026-05-05-lt2-literature-search-previous-topics.md` | LT-2 design spec — literature search, previous topics, knowledge library polish |
| `docs/superpowers/plans/2026-05-05-lt2-literature-search-previous-topics.md` | LT-2 implementation plan |
| `docs/superpowers/specs/2026-05-06-lt3-research-agent-scaffolding.md` | LT-3 design spec — research agent scaffolding, metrics, hypothesis drafts |
| `docs/superpowers/plans/2026-05-06-lt3-research-agent-scaffolding.md` | LT-3 implementation plan — task checklist and execution order |
| `docs/testsPlans/manualTestPlan_agent_lt1.md` | LT-1 manual test plan |
| `docs/testsPlans/manualTestPlan_pre_lt2_layout.md` | Pre-LT-2 manual test plan — layout, sidebar, input pinning |
| `docs/testsPlans/manualTestPlan_agent_lt2.md` | LT-2 manual test plan |
| `docs/testsPlans/manualTestPlan_agent_lt3.md` | LT-3 manual test plan — Neuro-Research mode, metrics, hypotheses |
| `docs/testsPlans/manualTestPlan_config_phase1.md` | Config Phase 1 manual test plan — per-agent model env var evals |
| `docs/superpowers/plans/2026-05-04-tech-debt-td1.md` | TD-1 plan |
| `docs/superpowers/plans/2026-05-04-tech-debt-td2.md` | TD-2 plan |
| `docs/superpowers/plans/2026-05-04-tech-debt-td3.md` | TD-3 plan |
