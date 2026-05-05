# NeuroDb — Project Status

**Last updated:** 2026-05-05
**Active focus:** Pre-LT-2 manual test ready — fixed-pane chat layout and sidebar migration
**Next:** Pre-LT-2 manual test sign-off
**Goal alignment:** Give the user a capable neuroscience learning partner — one that remembers what has been explored and builds on it, so learning compounds over time.

---

## Active Work — Learning Epoch

| Phase | Focus | Status |
|-------|-------|--------|
| LT-1 | BaseAgent architecture, NeuroDbAgent rename, mode rename, auto-session, NeuroTutorAgent core, knowledge library storage + UI | Complete — 255 tests — signed off 2026-05-05 |
| Pre-LT-2 | Fixed-pane layout (VSCode-style), input pinned to bottom, mode/chapter → sidebar, sidebar as extensible config panel | Manual test ready — 264 tests |
| LT-2 | LiteratureSearchClient (PubMed + Semantic Scholar), Previous Topics panel, sidebar config extensions, semantic dedup, Knowledge Library polish, connector visibility | Spec complete — implementation plan pending (starts after Pre-LT-2 ships) |
| LT-3 | Research agent scaffolding, knowledge growth metrics, hypothesis tools | Not started |
| CF-1 | Connector framework architecture — plugin system for adding connectors without rework | Planned post-LT-2 |

**Epoch plan:** `docs/ClaudeLearnEpochPlan.md`
**LT-1 spec:** `docs/superpowers/specs/2026-05-05-neuro-tutor-epoch-design.md`
**Pre-LT-2 spec:** `docs/superpowers/specs/2026-05-05-pre-lt2-chat-layout-hardening.md`
**LT-2 spec:** `docs/superpowers/specs/2026-05-05-lt2-literature-search-previous-topics.md`

---

## Tech Debt (complete)

| Sprint | Focus | Status |
|--------|-------|--------|
| TD-1 | Schema migration framework, connector fetch_by_id/search_by_keyword on all sources, explicit connector registry, StudyNote unique constraint, dependency pinning | Complete — 186 tests |
| TD-2 | Unit tests: embedder, enrichment, provenance; clear button behavioral tests | Complete — 204 tests |
| TD-3 | Dead code removal, model name env var, api_messages rollback on exception, QualityEvent compound index, chapter context guard, pytest-cov | Complete — 210 tests |

---

## Open Issues

See `docs/testLog.md`. Open items triaged for LT-2: LOG-001 (textbook dropdown ambiguity), LOG-002/003 (chat scroll/controls), LOG-004/005 (knowledge library card polish). LOG-006 (model visibility) deferred post-LT-2. LOG-007 (test plan clarity) resolved in planning.

---

## Completed

| Phase | What | Date |
|-------|------|------|
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
| `docs/testLog.md` | Running issue log — open and resolved items across all phases |
| `docs/superpowers/specs/2026-05-05-neuro-tutor-epoch-design.md` | LT-1 design spec |
| `docs/superpowers/plans/2026-05-05-lt1-neuro-tutor-foundation.md` | LT-1 implementation plan |
| `docs/superpowers/specs/2026-05-05-pre-lt2-chat-layout-hardening.md` | Pre-LT-2 design spec — fixed-pane layout, sidebar config panel |
| `docs/superpowers/plans/2026-05-05-pre-lt2-chat-layout-hardening.md` | Pre-LT-2 implementation plan — manual test ready, sign-off pending |
| `docs/superpowers/specs/2026-05-05-lt2-literature-search-previous-topics.md` | LT-2 design spec — literature search, previous topics, knowledge library polish |
| `docs/testsPlans/manualTestPlan_agent_lt1.md` | LT-1 manual test plan |
| `docs/testsPlans/manualTestPlan_pre_lt2_layout.md` | Pre-LT-2 manual test plan — layout, sidebar, input pinning |
| `docs/superpowers/plans/2026-05-04-tech-debt-td1.md` | TD-1 plan |
| `docs/superpowers/plans/2026-05-04-tech-debt-td2.md` | TD-2 plan |
| `docs/superpowers/plans/2026-05-04-tech-debt-td3.md` | TD-3 plan |
