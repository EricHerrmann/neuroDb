# NeuroDb — Project Status

**Last updated:** 2026-05-06
**Active focus:** LT-3 implementation complete — manual verification pending
**Next:** LT-3 manual test sign-off
**Goal alignment:** Give the user a capable neuroscience learning partner — one that remembers what has been explored and builds on it, so learning compounds over time.

---

## Active Work — Learning Epoch

| Phase | Focus | Status |
|-------|-------|--------|
| LT-1 | BaseAgent architecture, NeuroDbAgent rename, mode rename, auto-session, NeuroTutorAgent core, knowledge library storage + UI | Complete — 255 tests — signed off 2026-05-05 |
| Pre-LT-2 | Sidebar migration complete; fixed-pane Streamlit layout failed manual test and is deferred to UI shell architecture | Closed/deferred — 262 tests |
| LT-2 | LiteratureSearchClient (PubMed + Semantic Scholar), Previous Topics panel, sidebar config extensions, semantic dedup, Knowledge Library polish, connector visibility | Complete — 278 tests — signed off 2026-05-06 |
| LT-3 | Research agent scaffolding, knowledge growth metrics, hypothesis tools | Implemented — 307 tests — manual verification pending |
| UI Shell | UI tech-stack architecture for fixed workbench behavior after LT-2/LT-3 MVP capability maturity | Deferred post-LT-3 |
| CF-1 | Connector framework architecture — plugin system for adding connectors without rework | Planned post-LT-2 |

**Epoch plan:** `docs/ClaudeLearnEpochPlan.md`
**LT-1 spec:** `docs/superpowers/specs/2026-05-05-neuro-tutor-epoch-design.md`
**Pre-LT-2 spec:** `docs/superpowers/specs/2026-05-05-pre-lt2-chat-layout-hardening.md`
**LT-2 spec:** `docs/superpowers/specs/2026-05-05-lt2-literature-search-previous-topics.md`
**LT-3 spec:** `docs/superpowers/specs/2026-05-06-lt3-research-agent-scaffolding.md`
**LT-3 plan:** `docs/superpowers/plans/2026-05-06-lt3-research-agent-scaffolding.md`

---

## Tech Debt (complete)

| Sprint | Focus | Status |
|--------|-------|--------|
| TD-1 | Schema migration framework, connector fetch_by_id/search_by_keyword on all sources, explicit connector registry, StudyNote unique constraint, dependency pinning | Complete — 186 tests |
| TD-2 | Unit tests: embedder, enrichment, provenance; clear button behavioral tests | Complete — 204 tests |
| TD-3 | Dead code removal, model name env var, api_messages rollback on exception, QualityEvent compound index, chapter context guard, pytest-cov | Complete — 210 tests |

---

## Open Issues

See `docs/testLog.md`. Current open items: LOG-015 (agent session date — in LT-3 plan), LOG-021 (agent mode not persisted — in LT-3 plan), LOG-001 (textbook dropdown ambiguity — deferred post-LT-3), LOG-014 (Semantic Scholar API key policy — arch doc update), LOG-006 (model visibility — deferred post-LT-3), LOG-013 (UI shell rearchitecture — deferred post-LT-3).

---

## Completed

| Phase | What | Date |
|-------|------|------|
| LT-1 | BaseAgent architecture, NeuroTutorAgent, auto-session, Knowledge Library storage + UI | 2026-05-05 |
| LT-2 | Live literature search, Previous Topics, session memory, Knowledge Library polish | 2026-05-06 |
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
| `NeuroDbGoals.md` | Top-level project goals |
| `CLAUDE.md` | Engineering rules, process, environment |
| `docs/ClaudeLearnEpochPlan.md` | Learning Epoch plan — Neuro-Tutor, agent architecture pattern, phased roadmap |
| `docs/ClaudeDbEpochPlan.md` | DB epoch plan and architecture decisions |
| `docs/uiEpoch.md` | UI epoch plan — Streamlit constraints, FastAPI/React workbench migration path |
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
| `docs/superpowers/plans/2026-05-04-tech-debt-td1.md` | TD-1 plan |
| `docs/superpowers/plans/2026-05-04-tech-debt-td2.md` | TD-2 plan |
| `docs/superpowers/plans/2026-05-04-tech-debt-td3.md` | TD-3 plan |
