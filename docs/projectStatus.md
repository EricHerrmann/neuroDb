# NeuroDb — Project Status

**Last updated:** 2026-06-18
**Active focus:** Knowledge Library removal semantics — Remove should delete unreferenced papers and surface an explicit rationale plus delete/replace-reference choices when other project records still reference the paper. Manual gate: `docs/testsPlans/manualTestPlan_knowledge_library_remove_references.md`. Also pending: TeX ingest (`docs/testsPlans/manualTestPlan_tex_ingest.md`), Phase 2b OA PDF + generic-HTML (`docs/testsPlans/manualTestPlan_citation_phase2b_pdf_html.md`, PB1–PB8 + LF1–LF3), and the combined Phase 2a + Learning Plans + Phase 1 gate (`docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md`).
**Next:** Run manual gates — Phase 2b (PB1–PB8) and the combined Phase 2a + Learning Plans gate (AG1–AG5, FT1–FT8, LP1–LP8). Then pick up the literature source registry spec. **DEFERRED:** Phase 2b Docling high-fidelity PDF adapter — deferred to a future phase (PyMuPDF-first shipped); implement behind the `docling_convert` seam in `pdf_parser.py` when ready. Also deferred: drop the now-unused dead columns `research_questions.topic_id` and `study_notes.topic_id`/`concept_id` (retained to avoid a DuckDB table rebuild).
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

See `docs/testLog.md`. Current open items: LOG-001 (textbook dropdown ambiguity), LOG-050 (Gemini premium testing deferred), LOG-051 (UI icon pane association), LOG-057 (argument order tech debt), LOG-072 (Phase 2a verify_quote semantic-recall gap). Monitor item: LOG-060 (chat-turn hang, likely frontend streamed-Markdown renderer loop fixed; watch for recurrence).

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
| `docs/testsPlans/manualTestPlan_citation_phase1_abstract_grounding.md` | SUPERSEDED 2026-06-10 → redirects to the combined plan (Phase 1 cases are now Part A / AG1–AG5 there) |
| `docs/superpowers/specs/2026-06-05-learning-plans-design.md` | Learning Plans build-ready design spec — data model, proposed→confirmed lifecycle, read-paper-on-confirm, grouping anchor cross-reference, shared agent tools, API surface, Study Plan surface |
| `docs/superpowers/plans/2026-06-05-learning-plans.md` | Learning Plans implementation plan — 9 tasks (migration 022, store, confirm/dismiss, updates, grouping integration, agent tools, API routes, Study Plan UI, manual gate); implemented 2026-06-05, manual verification pending |
| `docs/superpowers/plans/2026-06-06-study-plan-workspace.md` | Study Plan workspace phased implementation plan — readable steps/naming, sectioned plans, plan-linked notes/chats, plan-primary workspace, agent plan operations |
| `docs/testsPlans/manualTestPlan_learning_plans.md` | SUPERSEDED 2026-06-10 → redirects to the combined plan (Learning Plans cases are now Part B / LP1–LP8 there) |
| **Deferred / Upcoming** | |
| `docs/superpowers/specs/2026-06-02-literature-source-registry-design.md` | Literature source backend registry design (Tutor epoch, Tech Debt TD-5) — SourceBackend protocol + registry list + JSON source_counts column so a new lit source is one file + one line; now unblocked (Groupings Phase 5 + Research Question Phase 1 complete) |
| `docs/superpowers/specs/2026-06-09-citation-grade-data-access-design.md` | Citation-grade data access design (Tutor epoch) — eight invariants: tiered ingestion (metadata/abstract/full_text), parse-quality gate, end-to-end provenance, retrieval threshold, quote verification, grounding disclosure, citable-intent full-text trigger, temporal trust modifier (vintage/cutoff/currency); swappable embedder; Phase 1 abstract grounding + Phase 2 full-text/provenance; pending user review |
| `docs/superpowers/plans/2026-06-09-citation-grade-phase1-abstract-grounding.md` | Citation-grade Phase 1 implementation plan — 8 tasks (manual plan, migration 023 data_tier/currency_status, temporal_descriptor helper, queue_source abstract/year capture, abstract-grounded summary, Chroma metadata, disclosure prompt/enrichment, verification); ready to execute |
| `docs/superpowers/specs/2026-06-10-citation-grade-phase2a-structured-fulltext-design.md` | Citation-grade Phase 2a design — thin slice of parent §6: structured-source full-text (arXiv HTML/LaTeX, PMC JATS, user-supplied clean text) fetch→chunk→embed into a second `knowledge_chunks` collection; dedicated `search_full_text` quote tool; fail-closed `verify_quote` + end-of-turn ledger backstop; synchronous acquire action; separate `FullTextBackend` (not blocking on the search registry); generic-HTML/PDF rejected to 2b; pending user review |
| `docs/superpowers/plans/2026-06-10-citation-grade-phase2a-structured-fulltext.md` | Citation-grade Phase 2a implementation plan — 14 tasks (migration 024 paper_chunks, chunking, full_text_client backends, chunk_store, quote_verify, full-text tools, agent wiring, ledger backstop, acquire route, React surface, manual gate); ready to execute |
| `docs/superpowers/specs/2026-06-12-citation-grade-phase2b-pdf-html-design.md` | Citation-grade Phase 2b design — fallback ladder after 2a declines: OA PDF discovery (Unpaywall + S2 openAccessPdf + landing-page `citation_pdf_url`/anchor scan, PMID→DOI) + generic-HTML extraction + user-supplied PDF/HTML URL or PDF upload; PyMuPDF-first parse (Docling deferred behind seam); confidence-tiered parse-quality gate (auto-accept / staged needs-review / reject); migration 025 (`parse_confidence`, `page` anchor, `paper_fulltext_staging`); status-driven acquire UI; OCR/embedder-upgrade/eval deferred to 2c; design approved, implementation complete |
| `docs/superpowers/plans/2026-06-12-citation-grade-phase2b-pdf-html.md` | Citation-grade Phase 2b implementation plan — 16 tasks (migration 025, ORM, chunking page anchor, ParsedArtifact, parse_quality gate, oa_locator, pdf_parser, html_extractor, fulltext_staging, phase2b orchestrator, full_text_client routing, async acquire + review endpoint, integration, chunk_store page, React acquire surface, manual gate); implemented 2026-06-13 |
| `docs/testsPlans/manualTestPlan_citation_phase2b_pdf_html.md` | Citation-grade Phase 2b manual gate (pending verification) — PB1–PB8: OA PubMed paper pending→verified + page anchor quote; landing-page citation_pdf_url PDF; user-supplied PDF URL; medium-confidence needs_review → Confirm and Reject; generic publisher HTML; non-OA/scanned → unavailable; re-acquire idempotency; verified-paper Re-acquire button. **LF1–LF3 (local-file source):** drop-folder PDF pending→verified + page anchor; Markdown file synchronous verified; path-traversal → 400 and missing file → 404 |
| `docs/testsPlans/manualTestPlan_knowledge_library_remove_references.md` | Knowledge Library removal manual gate — verifies hard delete for unreferenced papers, explicit reference-blocker rationale with delete/replace choices for referenced papers, and restore for legacy soft-removed papers |
| `docs/superpowers/specs/2026-06-13-knowledge-library-local-file-source-design.md` | Knowledge Library local-file source design — drop-folder library (`knowledge_library_files/`, gitignored) + `GET /library-files` + acquire `source_path` routed by extension (pdf→PyMuPDF/2b, txt/md→user-supplied-text, html→trafilatura/2b) through the existing gate; `library_store` path-traversal guard; file picker in the acquire UI; for ingesting manually-downloaded paywalled PDFs; design approved, implementation complete |
| `docs/superpowers/plans/2026-06-13-knowledge-library-local-file-source.md` | Knowledge Library local-file source implementation plan — drop-folder API, source_path routing, library_store guard, file picker UI, manual gate (LF1–LF3); implemented 2026-06-13 |
| `docs/superpowers/specs/2026-06-16-tex-ingest-design.md` | TeX ingest design spec |
| `docs/testsPlans/manualTestPlan_tex_ingest.md` | TeX ingest manual test plan |
| `docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md` | Combined manual gate (pending verification) — Part A AG1–AG5 (Citation Phase 1 abstract grounding) + Part B FT1–FT8 (Phase 2a full text) + Part C LP1–LP8 (Learning Plans); merged from the superseded standalone Phase 1 and Learning Plans plans |
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
