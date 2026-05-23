# NeuroDb — Project Status

**Last updated:** 2026-05-23
**Active focus:** Phase 5b — Evidence Lens, Dataset Honesty, Retract Lifecycle; implementation complete with Research panel UX clarification patch; manual verification in progress (T1-T4 passed, T5-T7 pending)
**Next:** Phase 5b manual verification (T5-T7); UI-5 common manual verification
**Goal alignment:** Two co-equal goals in a feedback loop — accumulate neuroscience understanding grounded in real data (Goal 1), and conduct structured neuroscience investigations using existing public datasets and good scientific method (Goal 2). See `NeuroDbGoals.md`.

---

## Epoch Status

| Epoch | Source | Maturity | Next |
|---|---|---|---|
| DB | `src/neurodb/db/`, `src/neurodb/connectors/` | MVP complete (phases 0–3, 9); Phase 2 manual signed off 2026-05-21; Phase 3 manual signed off 2026-05-21; full suite 641 passed / 15 pre-existing failures; Phase 9 T1-T4 manual passed | Entity resolution (7); broader Phase 9 source-aware enrichment |
| Agent Core | `src/neurodb/agents/` | Stable; Phase 4 context-mode mechanics implemented and signed off 2026-05-21; provider live-tool reliability gap identified | Coordinate provider capability validation with Config Control |
| Tutor | `src/neurodb/tutor/` | MVP complete (LT-1/2/3); Phase 4 context-mode prompt and bundle behavior signed off 2026-05-21 | Open backlog: LOG-001, LOG-006, LOG-030; Phase 2/3 manual verification |
| Research | `src/neurodb/research/` | Scaffolded (LT-3); Phase 3 claims/evidence/gaps complete; Phase 2/3 manual signed off 2026-05-21; Phase 4 grounded/contextual behavior signed off 2026-05-21 | Open backlog: LOG-037, LOG-045, LOG-048, LOG-053, LOG-061 |
| UI | `src/neurodb/ui/`, `src/neurodb/api/`, `frontend/` | UI-3 signed off 2026-05-13; UI-5 P1/P2/P3 implementation complete; Phase 4 API preference and stream contract signed off 2026-05-21; Phase 5a signed off 2026-05-21; Phase 5b implementation complete 2026-05-21; Research panel status help/collapsible UX patch added 2026-05-22; Phase 5b T1-T4 manual passed 2026-05-23; LOG-060 moved to monitor after likely renderer fix | Phase 5b manual verification (T5-T7); monitor LOG-060 recurrence |
| Config Control | `src/neurodb/config/` | Phase 5B complete; live validation found OpenAI Chat Completions + tools fails for `gpt-5.4`, Anthropic full Tutor tool path succeeds | Provider-by-provider live tool-call matrix; OpenAI Responses adapter design; then Phase 6 fallback/telemetry |
| Tech Debt | Cross-cutting | Planned — TD-1 CLI argument normalization started from LOG-057; TD-5 abstraction/extensibility review logged | TD-1 parser coverage, TD-2 keyword-only helper APIs, TD-5 reusable abstractions |

---

## Model Tier Table

Quality-aligned provider model assignments. Update this table and `neurodb_models.toml` together when provider models change. `last_verified_at` dates are in the TOML.

| Tier | Anthropic | OpenAI | Gemini | Groq | DeepSeek |
|---|---|---|---|---|---|
| **economy** | claude-haiku-4-5-20251001 | gpt-5.4-mini | gemini-2.5-flash-lite | llama-3.1-8b-instant | deepseek-chat |
| **standard** | claude-sonnet-4-6 | gpt-5.4 | gemini-2.5-flash | llama-3.3-70b-versatile | deepseek-chat |
| **premium** | claude-opus-4-7 | gpt-5.5 | gemini-2.5-pro | openai/gpt-oss-120b | deepseek-reasoner |

Default provider for all tiers is **anthropic**. Override per tier via `[routing]` section in `neurodb_models.toml`.
DeepSeek is wired (economy: `deepseek-chat`, standard: `deepseek-chat`, premium: `deepseek-reasoner`); `eval_status = "baseline"` — all 7 probe checks passed 2026-05-20.
Source of truth for model IDs: `neurodb_models.toml`.

---

## Open Issues

See `docs/testLog.md`. Current open items: LOG-001 (textbook dropdown ambiguity), LOG-006 (model visibility), LOG-013 (UI shell rearchitecture), LOG-037 (research-question actions), LOG-041 (session summary visibility), LOG-045 (research-to-knowledge-library bridge), LOG-047 (telemetry timestamp format), LOG-048 (dismiss draft hypothesis), LOG-050 (Gemini premium testing deferred), LOG-059 (study log inner join drops anchors), LOG-061 (no retract/remove lifecycle for evidence links, questions, papers, claims). Monitor item: LOG-060 (chat-turn hang, likely frontend streamed-Markdown renderer loop fixed; watch for recurrence).

---

## Key References

| Document | Purpose |
|----------|---------|
| **Goals / Process** | |
| `NeuroDbGoals.md` | Top-level project goals and feedback loop |
| `CLAUDE.md` | Engineering rules, process, environment |
| **Active Issues** | |
| `docs/testLog.md` | Running issue log — open and resolved items across all phases |
| **Epoch Architecture + Status** | |
| `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md` | Epoch architecture spec — six epochs, interface contracts, coupling rules, goal-to-epoch mapping |
| `docs/AgentCore_EpochPlan.md` | Agent Core epoch plan — BaseAgent architecture, three-method contract, configuration injection |
| `docs/Tutor_EpochPlan.md` | Tutor epoch plan — NeuroTutorAgent, Knowledge Library, session management, open backlog |
| `docs/Research_EpochPlan.md` | Research epoch plan — NeuroResearchAgent, hypothesis tools, hypothesis review, open backlog |
| `docs/ConfigControl_EpochPlan.md` | Config Control epoch plan — routing phases, provider adapters, telemetry, Phase 6 next |
| `docs/DB_EpochPlan.md` | DB epoch plan — connectors, schema ownership, phases 0–9 |
| `docs/UI_EpochPlan.md` | UI epoch plan — Streamlit MVP, FastAPI/React migration path, phases UI-0–5 |
| `docs/TechDebt_EpochPlan.md` | Tech Debt epoch plan — argument-order safety, keyword-only APIs, parser helpers, request/config objects, reusable abstractions |
| **Active Plans / Specs** | |
| `docs/superpowers/specs/2026-05-18-learning-research-memory-refocus-design.md` | Cross-epoch design spec — refocus NeuroDb as a learning/research memory system and fix shallow dataset sourcing through dataset research packets |
| `docs/superpowers/specs/2026-05-18-phase2-papers-topics-concepts-design.md` | Phase 2 design spec — rename KnowledgeSource → Paper, add topics/concepts tables, linking tables, StudyNote generalization, topic_store helper, Tutor agent tools |
| `docs/superpowers/specs/2026-05-19-phase3-claims-evidence-design.md` | Phase 3 design spec — claims, evidence_links, research_gaps tables, claim_store helper, research agent tools |
| `docs/superpowers/specs/2026-05-19-phase4-context-modes-evidence-boundaries-design.md` | Phase 4 design spec — context modes, shared context orchestrator, evidence-boundary prompts, context metadata |
| `docs/superpowers/plans/2026-05-19-phase3-claims-evidence.md` | Phase 3 implementation plan — 5 tasks: schema, migration, claim_store, agent tools, integration test |
| `docs/testsPlans/manualTestPlan_db_phase2_papers_topics.md` | DB Phase 2 manual test plan — T1-T8 passed; signed off 2026-05-21 (T7-T8 verified as Phase 4 carry-forward) |
| `docs/testsPlans/manualTestPlan_db_phase3_claims_evidence.md` | DB Phase 3 manual test plan — T1-T8 passed; signed off 2026-05-21 (T8 verified as Phase 4 carry-forward) |
| `docs/testsPlans/manualTestPlan_phase4_context_modes.md` | Phase 4 manual test plan — context-mode preferences, SSE context summaries, Tutor/Research evidence-boundary behavior; T1-T8 passed, signed off 2026-05-21 |
| `docs/superpowers/specs/2026-05-21-phase5a-focus-controls-design.md` | Phase 5a design spec — three-dropdown header, ThinkingBubble, Tooltip, useChat thinkingState/activeTool |
| `docs/superpowers/plans/2026-05-21-phase5a-focus-controls.md` | Phase 5a implementation spec — phased frontend plan for header controls, in-progress feedback, and verification |
| `docs/testsPlans/manualTestPlan_ui5_common_parity.md` | UI-5 common manual test plan — 8 evals covering P1/P2/P3; pending sign-off |
| `docs/testsPlans/manualTestPlan_phase5b_evidence_retract.md` | Phase 5b manual test plan — Evidence Lens, Dataset Honesty, Retract Lifecycle; T1-T4 passed, T5-T7 pending |
| `docs/superpowers/plans/2026-05-21-phase5b-evidence-lens-dataset-honesty-retract.md` | Phase 5b implementation plan |
| **History** | |
| `docs/archive/completedPhases.md` | Completed phases and tech debt sprints — full history |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase5a_focus_controls.md` | Phase 5a manual test plan — T1-T10 passed and signed off 2026-05-21 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_db_phase9_dataset_research_packets.md` | DB Phase 9 manual test plan — T1-T4 passed and signed off 2026-05-18 |
