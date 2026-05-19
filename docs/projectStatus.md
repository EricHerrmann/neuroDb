# NeuroDb — Project Status

**Last updated:** 2026-05-19
**Active focus:** Phase 2 DB+Tutor implementation complete — DB schema, topic_store, Tutor agent extensions; awaiting Phase 2 manual verification
**Next:** Phase 2 manual verification and sign-off
**Goal alignment:** Two co-equal goals in a feedback loop — accumulate neuroscience understanding grounded in real data (Goal 1), and conduct structured neuroscience investigations using existing public datasets and good scientific method (Goal 2). See `NeuroDbGoals.md`.

---

## Epoch Status

| Epoch | Source | Maturity | Next |
|---|---|---|---|
| DB | `src/neurodb/db/`, `src/neurodb/connectors/` | MVP complete (phases 0–2, 9); Phase 2 (topics/concepts/papers/study-notes) signed off 2026-05-18 — 36 focused DB tests pass; full suite 573 passed / 9 config-routing failures; Phase 9 T1-T4 manual passed | Phase 2 manual verification, entity resolution (7), research storage schema (8), broader Phase 9 source-aware enrichment |
| Agent Core | `src/neurodb/agents/` | Stable | Config Control Phases 1–4 signed off; Phase 6 may add fallback chain logic |
| Tutor | `src/neurodb/tutor/` | MVP complete (LT-1/2/3) | Open backlog: LOG-001, LOG-006, LOG-030 |
| Research | `src/neurodb/research/` | Scaffolded (LT-3); hypothesis review with structured tool-use output | Research run management, research question actions (LOG-037) |
| UI | `src/neurodb/ui/`, `src/neurodb/api/`, `frontend/` | UI-3 signed off 2026-05-13; UI-5 P1/P2/P3 implementation complete — 516 Python tests, 58 frontend tests, build passed; common manual plan active | Common UI-5 manual verification |
| Config Control | `src/neurodb/config/` | Phase 5B complete — 398 automated tests; Phase 4 signed off 2026-05-09 | Phase 6: constructor fallback chain, SystemWarning table, CLI surface |
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
DeepSeek is wired (economy: `deepseek-chat`, standard: `deepseek-chat`, premium: `deepseek-reasoner`); `eval_status = "unverified"` — not yet validated.
Source of truth for model IDs: `neurodb_models.toml`.

---

## Open Issues

See `docs/testLog.md`. Current open items: LOG-001 (textbook dropdown ambiguity), LOG-006 (model visibility), LOG-013 (UI shell rearchitecture), LOG-030 (header/title sizing), LOG-037 (research-question actions), LOG-041 (session summary visibility), LOG-045 (research-to-knowledge-library bridge), LOG-047 (telemetry timestamp format), LOG-048 (dismiss draft hypothesis), LOG-050 (Gemini premium testing deferred).

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
| `docs/superpowers/plans/2026-05-19-phase3-claims-evidence.md` | Phase 3 implementation plan — 5 tasks: schema, migration, claim_store, agent tools, integration test |
| `docs/testsPlans/manualTestPlan_db_phase2_papers_topics.md` | DB Phase 2 manual test plan — T1-T8 covering migration, topic_store, StudyNote anchors, Tutor agent tools; pending sign-off |
| `docs/testsPlans/manualTestPlan_db_phase3_claims_evidence.md` | DB Phase 3 manual test plan — T1-T8 covering migration, claim_store, evidence links, gaps, question bundle, research agent tools; pending sign-off |
| `docs/testsPlans/manualTestPlan_ui5_common_parity.md` | UI-5 common manual test plan — 8 evals covering P1/P2/P3; pending sign-off |
| **History** | |
| `docs/archive/completedPhases.md` | Completed phases and tech debt sprints — full history |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_db_phase9_dataset_research_packets.md` | DB Phase 9 manual test plan — T1-T4 passed and signed off 2026-05-18 |
