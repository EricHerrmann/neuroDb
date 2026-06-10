# NeuroDb — Project Status

**Last updated:** 2026-06-10
**Active focus:** Citation-Grade Phase 2a (structured-source full-text RAG) — implementation complete; manual verification pending. Structured full-text acquisition (arXiv HTML/LaTeX, PMC JATS, user-supplied clean text) behind migration 024 (`paper_chunks` + `full_text_status`/`text_source`), a second `knowledge_chunks` Chroma collection, a dedicated `search_full_text` quote tool, fail-closed `verify_quote` + end-of-turn ledger backstop on both agents, and an "Acquire full text" Knowledge Library surface with tier/status badges. Backend 928 tests green (2 pre-existing `test_neuro_atlas_data` failures unrelated to this work); frontend 112 tests green and build clean. Manual gate is `docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md`. Prior: Learning Plans (migration 022) implementation complete, manual verification still pending via `docs/testsPlans/manualTestPlan_learning_plans.md`.
**Next:** Sign off Learning Plans via its manual test plan, then pick up the literature source registry spec. Deferred: drop the now-unused dead columns `research_questions.topic_id` and `study_notes.topic_id`/`concept_id` (retained to avoid a DuckDB table rebuild).
**Goal alignment:** Two co-equal goals in a feedback loop — accumulate neuroscience understanding grounded in real data (Goal 1), and conduct structured neuroscience investigations using existing public datasets and good scientific method (Goal 2). See `NeuroDbGoals.md`.

---

## Epoch Status

| Epoch | Source | Maturity | Next |
|---|---|---|---|
| DB | `src/neurodb/db/`, `src/neurodb/connectors/` | MVP complete (phases 0–3, 9); Phase 2 manual signed off 2026-05-21; Phase 3 manual signed off 2026-05-21; Phase 9 T1-T4 manual passed; Memory Refocus Completion fixed LOG-059 and passed manual T1-T5 on 2026-05-24 | Entity resolution (7); broader Phase 9 source-aware enrichment |
| Agent Core | `src/neurodb/agents/` | Stable; Phase 4 context-mode mechanics implemented and signed off 2026-05-21; Config Control Phase 6 added provider capability gating; Memory Refocus Completion added context budgets and retrieval telemetry | Coordinate provider live-tool validation with Config Control |
| Tutor | `src/neurodb/tutor/` | MVP complete (LT-1/2/3); Learning and Research Memory Refocus complete through Phase 6; Phase 2/3 manual verification and Phase 4 context-mode prompt behavior signed off 2026-05-21; active model visibility resolved in Config Control Phase 6 | Open backlog: LOG-001 |
| Research | `src/neurodb/research/` | Scaffolded (LT-3); Phase 3 claims/evidence/gaps complete; Phase 2/3 manual signed off 2026-05-21; Phase 4 grounded/contextual behavior signed off 2026-05-21; lifecycle UI gaps from LOG-037, LOG-048, and LOG-061 resolved in Phase 5b; queue/tool gaps from LOG-045 and LOG-053 resolved; dataset usefulness surfaced to agents in Memory Refocus Completion; Unified Groupings Phases 1–5 complete and signed off 2026-06-04; Research Question Phase 1 complete via the unified groupings engine and final Phase 5 post-drop T3 verification; Learning Plans implemented behind migration 022 (store, agent tools on tutor + research, `/api/research/plans` routes, Study Plan UI) — manual verification pending | Sign off Learning Plans; then literature source registry; deferred: drop unused legacy dead columns |
| UI | `frontend/`, `src/neurodb/api/`, legacy `src/neurodb/ui/` | UI-3 signed off 2026-05-13; UI-5 P1/P2/P3 complete and common manual testing passed 2026-05-23; UI-4 Streamlit deprecation complete 2026-06-09; React/FastAPI is primary; Streamlit is legacy compatibility only; LOG-060 moved to monitor after likely renderer fix | No active UI phase; monitor LOG-060 recurrence |
| Config Control | `src/neurodb/config/` | Phase 5B complete; Phase 6 complete and signed off 2026-05-23 with focused backend, call-site, frontend, ruff, compile, and manual T1-T5 checks passing | No active Config Control phase |
| Tech Debt | Cross-cutting | Planned — TD-1 CLI argument normalization started from LOG-057; TD-5 abstraction/extensibility review logged | TD-1 parser coverage, TD-2 keyword-only helper APIs, TD-5 reusable abstractions |

---

## Model Tier Table

Quality-aligned provider model assignments. Update this table and `neurodb_models.toml` together when provider models change. `last_verified_at` dates are in the TOML.

| Tier | Anthropic | OpenAI | Gemini | Groq | DeepSeek |
|---|---|---|---|---|---|
| **economy** | claude-haiku-4-5-20251001 | gpt-5.4-mini | gemini-3.1-flash-lite | llama-3.1-8b-instant | deepseek-v4-flash |
| **standard** | claude-sonnet-4-6 | gpt-5.4 | gemini-3.5-flash | llama-3.3-70b-versatile | deepseek-v4-flash |
| **premium** | claude-opus-4-8 | gpt-5.5 | gemini-3.1-pro-preview | openai/gpt-oss-120b | deepseek-v4-pro |

Default provider for all tiers is **anthropic**. Override per tier via `[routing]` section in `neurodb_models.toml`.
DeepSeek is wired (economy/standard: `deepseek-v4-flash`, premium: `deepseek-v4-pro`); previous aliases `deepseek-chat` and `deepseek-reasoner` are deprecated by provider docs for 2026-07-24.
Source of truth for model IDs: `neurodb_models.toml`.

---

## Open Issues

See `docs/testLog.md`. Current open items: LOG-001 (textbook dropdown ambiguity), LOG-050 (Gemini premium testing deferred), LOG-051 (UI icon pane association), LOG-057 (argument order tech debt). Monitor item: LOG-060 (chat-turn hang, likely frontend streamed-Markdown renderer loop fixed; watch for recurrence).

---

## Key References

| Document | Purpose |
|----------|---------|
| **Goals / Process** | |
| `NeuroDbGoals.md` | Top-level project goals and feedback loop |
| `CLAUDE.md` | Engineering rules, process, environment |
| `docs/agent_behavior.md` | Shared user-facing behavior instructions loaded into NeuroTutor and NeuroResearch prompts |
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
| `docs/UI_EpochPlan.md` | UI epoch plan — FastAPI/React primary workbench, deprecated Streamlit compatibility surface, phases UI-0–5 |
| `docs/TechDebt_EpochPlan.md` | Tech Debt epoch plan — argument-order safety, keyword-only APIs, parser helpers, request/config objects, reusable abstractions |
| **Active Plans / Specs** | |
| `docs/testsPlans/manualTestPlan_citation_phase1_abstract_grounding.md` | Citation-grade Phase 1 manual test plan — T1-T5 abstract capture, abstract-grounded summary, tier/vintage/currency disclosure; pending implementation |
| `docs/superpowers/specs/2026-06-05-learning-plans-design.md` | Learning Plans build-ready design spec — data model, proposed→confirmed lifecycle, read-paper-on-confirm, grouping anchor cross-reference, shared agent tools, API surface, Study Plan surface |
| `docs/superpowers/plans/2026-06-05-learning-plans.md` | Learning Plans implementation plan — 9 tasks (migration 022, store, confirm/dismiss, updates, grouping integration, agent tools, API routes, Study Plan UI, manual gate); implemented 2026-06-05, manual verification pending |
| `docs/superpowers/plans/2026-06-06-study-plan-workspace.md` | Study Plan workspace phased implementation plan — readable steps/naming, sectioned plans, plan-linked notes/chats, plan-primary workspace, agent plan operations |
| `docs/testsPlans/manualTestPlan_learning_plans.md` | Learning Plans manual test plan — T1-T8 through the Study Plan panel (tutor/research propose, confirm, dismiss-leaves-no-artifacts, progress, agent update, cross-reference, edit/delete); pending verification |
| **Deferred / Upcoming** | |
| `docs/superpowers/specs/2026-06-02-literature-source-registry-design.md` | Literature source backend registry design (Tutor epoch, Tech Debt TD-5) — SourceBackend protocol + registry list + JSON source_counts column so a new lit source is one file + one line; now unblocked (Groupings Phase 5 + Research Question Phase 1 complete) |
| `docs/superpowers/specs/2026-06-09-citation-grade-data-access-design.md` | Citation-grade data access design (Tutor epoch) — eight invariants: tiered ingestion (metadata/abstract/full_text), parse-quality gate, end-to-end provenance, retrieval threshold, quote verification, grounding disclosure, citable-intent full-text trigger, temporal trust modifier (vintage/cutoff/currency); swappable embedder; Phase 1 abstract grounding + Phase 2 full-text/provenance; pending user review |
| `docs/superpowers/plans/2026-06-09-citation-grade-phase1-abstract-grounding.md` | Citation-grade Phase 1 implementation plan — 8 tasks (manual plan, migration 023 data_tier/currency_status, temporal_descriptor helper, queue_source abstract/year capture, abstract-grounded summary, Chroma metadata, disclosure prompt/enrichment, verification); ready to execute |
| `docs/superpowers/specs/2026-06-10-citation-grade-phase2a-structured-fulltext-design.md` | Citation-grade Phase 2a design — thin slice of parent §6: structured-source full-text (arXiv HTML/LaTeX, PMC JATS, user-supplied clean text) fetch→chunk→embed into a second `knowledge_chunks` collection; dedicated `search_full_text` quote tool; fail-closed `verify_quote` + end-of-turn ledger backstop; synchronous acquire action; separate `FullTextBackend` (not blocking on the search registry); generic-HTML/PDF rejected to 2b; pending user review |
| `docs/superpowers/plans/2026-06-10-citation-grade-phase2a-structured-fulltext.md` | Citation-grade Phase 2a implementation plan — 14 tasks (migration 024 paper_chunks, chunking, full_text_client backends, chunk_store, quote_verify, full-text tools, agent wiring, ledger backstop, acquire route, React surface, manual gate); ready to execute |
| `docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md` | Citation-grade Phase 2a manual test plan — T1-T8 acquire/quote/verify/idempotency; pending implementation |
| `docs/citationGradeDesign.md` | Verbatim discussion capture that motivated the citation-grade data access spec (superseded by the 2026-06-09 design) |
| **History** | |
| `docs/archive/completedPhases.md` | Completed phases and tech debt sprints — full history |
| `docs/superpowers/specs/2026-06-02-learning-plans-design.md` | SUPERSEDED by the 2026-06-05 build-ready Learning Plans spec — original feature capture & design (retained for history) |
| `docs/superpowers/specs/2026-05-18-learning-research-memory-refocus-design.md` | Completed Learning and Research Memory Refocus design spec — Phases 1-6 complete through Memory Refocus Completion, signed off 2026-05-24 |
| `docs/superpowers/specs/2026-05-18-phase2-papers-topics-concepts-design.md` | Completed Phase 2 design spec — papers/topics/concepts/study context, signed off 2026-05-21 |
| `docs/superpowers/plans/2026-05-18-phase2-papers-topics-concepts.md` | Completed Phase 2 implementation plan — papers/topics/concepts/study context |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_db_phase2_papers_topics.md` | DB Phase 2 manual test plan — T1-T8 passed and signed off 2026-05-21 |
| `docs/superpowers/specs/2026-05-19-phase3-claims-evidence-design.md` | Completed Phase 3 design spec — claims, evidence links, research gaps, and question bundles, signed off 2026-05-21 |
| `docs/superpowers/plans/2026-05-19-phase3-claims-evidence.md` | Completed Phase 3 implementation plan — schema, migration, claim_store, agent tools, integration tests |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_db_phase3_claims_evidence.md` | DB Phase 3 manual test plan — T1-T8 passed and signed off 2026-05-21 |
| `docs/superpowers/specs/2026-05-19-phase4-context-modes-evidence-boundaries-design.md` | Completed Phase 4 design spec — context modes, shared context orchestrator, evidence-boundary prompts, signed off 2026-05-21 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase4_context_modes.md` | Phase 4 manual test plan — T1-T8 passed and signed off 2026-05-21 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_ui5_common_parity.md` | UI-5 common manual test plan — T1-T8 passed and signed off 2026-05-23 |
| `docs/superpowers/specs/2026-05-21-phase5a-focus-controls-design.md` | Completed Phase 5a design spec — focus controls and in-progress feedback, signed off 2026-05-21 |
| `docs/superpowers/plans/2026-05-21-phase5a-focus-controls.md` | Completed Phase 5a implementation plan — header controls, in-progress feedback, and verification |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase5a_focus_controls.md` | Phase 5a manual test plan — T1-T10 passed and signed off 2026-05-21 |
| `docs/superpowers/specs/2026-05-21-phase5b-evidence-lens-dataset-honesty-retract-design.md` | Completed Phase 5b design spec — evidence lens, dataset honesty, and retract lifecycle, signed off 2026-05-23 |
| `docs/superpowers/plans/2026-05-21-phase5b-evidence-lens-dataset-honesty-retract.md` | Completed Phase 5b implementation plan — evidence lens, dataset honesty, and lifecycle status transitions |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase5b_evidence_retract.md` | Phase 5b manual test plan — T1-T7 passed and signed off 2026-05-23 |
| `docs/superpowers/specs/2026-05-23-phase6-fallback-telemetry-design.md` | Config Control Phase 6 design spec — provider fallback, system warnings, telemetry CLI, UI visibility |
| `docs/superpowers/plans/2026-05-23-phase6-fallback-telemetry.md` | Config Control Phase 6 implementation plan — complete and signed off 2026-05-23 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6_fallback_telemetry.md` | Config Control Phase 6 manual test plan — T1-T5 passed and signed off 2026-05-23 |
| `docs/superpowers/specs/2026-05-23-memory-refocus-completion-design.md` | Completion phase spec — context budgets, retrieval telemetry, task-type defaults, LOG-059 study log outer join, LOG-054 dataset usefulness |
| `docs/superpowers/plans/2026-05-23-memory-refocus-completion.md` | Completion phase implementation plan — complete and signed off 2026-05-24 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_memory_refocus_completion.md` | Completion phase manual test plan — T1-T5 passed and signed off 2026-05-24 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_db_phase9_dataset_research_packets.md` | DB Phase 9 manual test plan — T1-T4 passed and signed off 2026-05-18 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_groupings_phase3b.md` | Groupings Phase 3b manual test plan — T1-T3 passed and signed off 2026-06-02 (T2 surfaced LOG-063, fixed via migration 019) |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_groupings_phase4.md` | Groupings Phase 4 manual test plan — T1-T7 passed and signed off 2026-06-04 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_groupings_phase5.md` | Groupings Phase 5 manual test plan — T1-T4 passed and signed off 2026-06-04; final post-drop gate for unified groupings and Research Question Phase 1 |
| `docs/superpowers/specs/2026-06-01-unified-groupings-taxonomy-design.md` | Completed unified groupings taxonomy design — single groupings/grouping_links model (topic/concept/future), hierarchy, semantic+proposal matching; Phases 1–5 complete; closed LOG-062 |
| `docs/superpowers/plans/2026-06-01-groupings-phase1-unified-tables.md` | Completed Groupings Phase 1 plan — unified tables + migration 017 backfill; implemented 2026-06-01 |
| `docs/superpowers/plans/2026-06-01-groupings-phase2-engine.md` | Completed Groupings Phase 2 plan — type-agnostic engine (store functions, type registry, single-level hierarchy guard, rollups); implemented 2026-06-01 |
| `docs/superpowers/specs/2026-06-01-groupings-phase3-question-cutover-design.md` | Completed Groupings Phase 3 design — question cutover, semantic/proposal matcher, /groupings routes, migration 018 |
| `docs/superpowers/plans/2026-06-01-groupings-phase3a-backend-cutover.md` | Completed Groupings Phase 3a plan — matcher, routes, question-flow cutover, proposal lifecycle; implemented 2026-06-01 |
| `docs/archive/manualTestPlan_groupings_phase3a_superseded.md` | Superseded Groupings Phase 3a manual test plan — backend cutover behavior later verified through Groupings Phase 3b/4/5 |
| `docs/superpowers/plans/2026-06-01-groupings-phase3b-ui.md` | Completed Groupings Phase 3b UI plan — filter repoint to /groupings, proposal "new" chips, topic hierarchy curation; implemented 2026-06-02 |
| `docs/superpowers/plans/2026-06-02-groupings-phase4-consumer-migration.md` | Completed Groupings Phase 4 plan — all consumers onto the engine; LOG-064/065/066 closed; manual T1-T7 signed off 2026-06-04 |
| `docs/superpowers/specs/2026-06-04-groupings-phase5-legacy-drop-design.md` | Completed Groupings Phase 5 design — hard-drop legacy `topics`/`concepts` + six join tables (migration 021), 017 backfill guard, straggler cutover; signed off 2026-06-04 |
| `docs/superpowers/plans/2026-06-04-groupings-phase5-legacy-drop.md` | Completed Groupings Phase 5 plan — 8 tasks (017 guard, consumer cutover, model removal, migration 021 drop); backend 814 tests green and manual T1-T4 passed 2026-06-04 |
| `docs/superpowers/specs/2026-06-01-topic-taxonomy-hierarchy-design.md` | SUPERSEDED by the unified-groupings spec — topics-only hierarchy (retained for history) |
| `docs/superpowers/specs/2026-06-01-research-question-phase1-design.md` | Completed Research Question Phase 1 design — capture/categorize, suggestions, topic filter, delete cascade delivered through the unified groupings engine and signed off by Phase 5 T3 |
| `docs/superpowers/plans/2026-06-01-research-question-phase1.md` | Research Question Phase 1 plan (10 tasks) — superseded; capability delivered via the unified groupings engine and final post-drop smoke |
| `docs/archive/manualTestPlan_research_question_phase1_superseded.md` | Research Question Phase 1 manual test plan — SUPERSEDED / never executed; workflows verified via groupings 3b/4 manual plans + Phase 5 T3 (see banner) |
