# NeuroDb — Project Status

**Last updated:** 2026-05-31
**Active focus:** Tech Debt epoch (TD-1 CLI argument normalization, TD-2 keyword-only helper APIs)
**Next:** Tech Debt sprint planning and implementation
**Goal alignment:** Two co-equal goals in a feedback loop — accumulate neuroscience understanding grounded in real data (Goal 1), and conduct structured neuroscience investigations using existing public datasets and good scientific method (Goal 2). See `NeuroDbGoals.md`.

---

## Epoch Status

| Epoch | Source | Maturity | Next |
|---|---|---|---|
| DB | `src/neurodb/db/`, `src/neurodb/connectors/` | MVP complete (phases 0–3, 9); Phase 2 manual signed off 2026-05-21; Phase 3 manual signed off 2026-05-21; Phase 9 T1-T4 manual passed; Memory Refocus Completion fixed LOG-059 and passed manual T1-T5 on 2026-05-24 | Entity resolution (7); broader Phase 9 source-aware enrichment |
| Agent Core | `src/neurodb/agents/` | Stable; Phase 4 context-mode mechanics implemented and signed off 2026-05-21; Config Control Phase 6 added provider capability gating; Memory Refocus Completion added context budgets and retrieval telemetry | Coordinate provider live-tool validation with Config Control |
| Tutor | `src/neurodb/tutor/` | MVP complete (LT-1/2/3); Phase 4 context-mode prompt and bundle behavior signed off 2026-05-21; active model visibility resolved in Config Control Phase 6 | Open backlog: LOG-001; Phase 2/3 manual verification |
| Research | `src/neurodb/research/` | Scaffolded (LT-3); Phase 3 claims/evidence/gaps complete; Phase 2/3 manual signed off 2026-05-21; Phase 4 grounded/contextual behavior signed off 2026-05-21; lifecycle UI gaps from LOG-037, LOG-048, and LOG-061 resolved in Phase 5b; queue/tool gaps from LOG-045 and LOG-053 resolved; dataset usefulness surfaced to agents in Memory Refocus Completion | Research Question Phase 1 in implementation |
| UI | `src/neurodb/ui/`, `src/neurodb/api/`, `frontend/` | UI-3 signed off 2026-05-13; UI-5 P1/P2/P3 complete and common manual testing passed 2026-05-23; Phase 4 API preference and stream contract signed off 2026-05-21; Phase 5a signed off 2026-05-21; Phase 5b signed off 2026-05-23 (T1-T7 passed); DuckDB FK update limitation resolved via migration 012; LOG-060 moved to monitor after likely renderer fix | No active UI phase; monitor LOG-060 recurrence |
| Config Control | `src/neurodb/config/` | Phase 5B complete; Phase 6 complete and signed off 2026-05-23 with focused backend, call-site, frontend, ruff, compile, and manual T1-T5 checks passing | No active Config Control phase |
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

See `docs/testLog.md`. Current open items: LOG-001 (textbook dropdown ambiguity), LOG-013 (UI shell rearchitecture), LOG-050 (Gemini premium testing deferred), LOG-051 (UI icon pane association), LOG-057 (argument order tech debt). Monitor item: LOG-060 (chat-turn hang, likely frontend streamed-Markdown renderer loop fixed; watch for recurrence).

---

## Key References

| Document | Purpose |
|----------|---------|
| **Goals / Process** | |
| `NeuroDbGoals.md` | Top-level project goals and feedback loop |
| `CLAUDE.md` | Engineering rules, process, environment |
| `docs/OrganizingResearchQuestionsCodex.md` | Codex review of current NeuroDb capabilities and next steps for organizing, remembering, categorizing, creating, and tutoring research questions |
| `docs/OrganizingResearchQuestionsClaude.md` | Claude review: lifecycle mapping, gap analysis, and recommended next capabilities for research question management |
| `docs/OrganizingResearchQuestionsCodexReview.md` | Codex comparison of Claude and Codex research-question workflow notes |
| `docs/researchQuestionDesignCodex.md` | Codex phased design plan for first-class research-question capture, categorization, source/dataset linking, Socratic exploration, recall, and hypothesis promotion |
| **Active Issues** | |
| `docs/testLog.md` | Running issue log — open and resolved items across all phases |
| **Epoch Architecture + Status** | |
| `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md` | Epoch architecture spec — six epochs, interface contracts, coupling rules, goal-to-epoch mapping |
| `docs/AgentCore_EpochPlan.md` | Agent Core epoch plan — BaseAgent architecture, three-method contract, configuration injection |
| `docs/Tutor_EpochPlan.md` | Tutor epoch plan — NeuroTutorAgent, Knowledge Library, session management, open backlog |
| `docs/Research_EpochPlan.md` | Research epoch plan — NeuroResearchAgent, hypothesis tools, hypothesis review, open backlog |
| `docs/ConfigControl_EpochPlan.md` | Config Control epoch plan — routing phases, provider adapters, telemetry |
| `docs/DB_EpochPlan.md` | DB epoch plan — connectors, schema ownership, phases 0–9 |
| `docs/UI_EpochPlan.md` | UI epoch plan — Streamlit MVP, FastAPI/React migration path, phases UI-0–5 |
| `docs/TechDebt_EpochPlan.md` | Tech Debt epoch plan — argument-order safety, keyword-only APIs, parser helpers, request/config objects, reusable abstractions |
| **Active Plans / Specs** | |
| `docs/superpowers/specs/2026-06-01-research-question-phase1-design.md` | Research Question Phase 1 design spec — capture & categorize questions, topic/concept suggestion, UI lifecycle |
| `docs/superpowers/specs/2026-06-01-topic-taxonomy-hierarchy-design.md` | Topic taxonomy hierarchy design spec — parent/child topics (parent_id), hierarchy-aware question→topic suggestion rollup, parent-filter descendants, curation UI |
| `docs/superpowers/plans/2026-06-01-research-question-phase1.md` | Research Question Phase 1 implementation plan — 10 tasks |
| `docs/testsPlans/manualTestPlan_research_question_phase1.md` | Research Question Phase 1 manual test plan — T1-T6 |
| `docs/superpowers/specs/2026-05-18-learning-research-memory-refocus-design.md` | Cross-epoch design spec — refocus NeuroDb as a learning/research memory system and fix shallow dataset sourcing through dataset research packets |
| `docs/superpowers/specs/2026-05-18-phase2-papers-topics-concepts-design.md` | Phase 2 design spec — rename KnowledgeSource → Paper, add topics/concepts tables, linking tables, StudyNote generalization, topic_store helper, Tutor agent tools |
| `docs/superpowers/specs/2026-05-19-phase3-claims-evidence-design.md` | Phase 3 design spec — claims, evidence_links, research_gaps tables, claim_store helper, research agent tools |
| `docs/superpowers/specs/2026-05-19-phase4-context-modes-evidence-boundaries-design.md` | Phase 4 design spec — context modes, shared context orchestrator, evidence-boundary prompts, context metadata |
| `docs/superpowers/plans/2026-05-19-phase3-claims-evidence.md` | Phase 3 implementation plan — 5 tasks: schema, migration, claim_store, agent tools, integration test |
| `docs/testsPlans/manualTestPlan_db_phase2_papers_topics.md` | DB Phase 2 manual test plan — T1-T8 passed; signed off 2026-05-21 (T7-T8 verified as Phase 4 carry-forward) |
| `docs/testsPlans/manualTestPlan_db_phase3_claims_evidence.md` | DB Phase 3 manual test plan — T1-T8 passed; signed off 2026-05-21 (T8 verified as Phase 4 carry-forward) |
| `docs/testsPlans/manualTestPlan_phase4_context_modes.md` | Phase 4 manual test plan — context-mode preferences, SSE context summaries, Tutor/Research evidence-boundary behavior; T1-T8 passed, signed off 2026-05-21 |
| **History** | |
| `docs/archive/completedPhases.md` | Completed phases and tech debt sprints — full history |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_ui5_common_parity.md` | UI-5 common manual test plan — T1-T8 passed and signed off 2026-05-23 |
| `docs/superpowers/specs/2026-05-21-phase5a-focus-controls-design.md` | Phase 5a design spec — three-dropdown header, ThinkingBubble, Tooltip, useChat thinkingState/activeTool |
| `docs/superpowers/plans/2026-05-21-phase5a-focus-controls.md` | Phase 5a implementation spec — phased frontend plan for header controls, in-progress feedback, and verification |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase5a_focus_controls.md` | Phase 5a manual test plan — T1-T10 passed and signed off 2026-05-21 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase5b_evidence_retract.md` | Phase 5b manual test plan — T1-T7 passed and signed off 2026-05-23 |
| `docs/superpowers/specs/2026-05-23-phase6-fallback-telemetry-design.md` | Config Control Phase 6 design spec — provider fallback, system warnings, telemetry CLI, UI visibility |
| `docs/superpowers/plans/2026-05-23-phase6-fallback-telemetry.md` | Config Control Phase 6 implementation plan — complete and signed off 2026-05-23 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6_fallback_telemetry.md` | Config Control Phase 6 manual test plan — T1-T5 passed and signed off 2026-05-23 |
| `docs/superpowers/specs/2026-05-23-memory-refocus-completion-design.md` | Completion phase spec — context budgets, retrieval telemetry, task-type defaults, LOG-059 study log outer join, LOG-054 dataset usefulness |
| `docs/superpowers/plans/2026-05-23-memory-refocus-completion.md` | Completion phase implementation plan — complete and signed off 2026-05-24 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_memory_refocus_completion.md` | Completion phase manual test plan — T1-T5 passed and signed off 2026-05-24 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_db_phase9_dataset_research_packets.md` | DB Phase 9 manual test plan — T1-T4 passed and signed off 2026-05-18 |
