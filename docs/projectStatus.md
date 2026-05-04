# NeuroDb — Project Status

**Last updated:** 2026-05-04
**Active focus:** Tech Debt sprints TD-1, TD-2, TD-3
**Next:** P7 — TBD (entity resolution or hypothesis layer; scoped after TD complete)
**Goal alignment:** Building a trustworthy, reproducible neuroscience data platform with an agentic learning layer grounded in ingested dataset IDs.

---

## Active Work — Tech Debt Sprints

| Sprint | Focus | Status |
|--------|-------|--------|
| TD-1 | Schema migration framework, connector fetch_by_id/search_by_keyword on all sources, explicit connector registry, StudyNote unique constraint, dependency pinning | Complete — 186 tests |
| TD-2 | Unit tests: embedder, enrichment, provenance; clear button behavioral tests | Not started |
| TD-3 | Dead code removal, model name env var, api_messages rollback on exception, QualityEvent compound index, chapter context guard, pytest-cov | Not started |

**Implementation plans:** `docs/superpowers/plans/2026-05-04-tech-debt-td1.md`, `td2.md`, `td3.md`

---

## Open Issues

See `docs/testLog.md`. Current open items: T4-clear (chat history transient clear), P6-selector (textbook dropdown ambiguity). Both non-blocking.

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
| `docs/ClaudeDbEpochPlan.md` | DB epoch plan and architecture decisions |
| `docs/testLog.md` | Running issue log — open and resolved items across all phases |
| `docs/superpowers/plans/2026-05-04-tech-debt-td1.md` | TD-1 plan |
| `docs/superpowers/plans/2026-05-04-tech-debt-td2.md` | TD-2 plan |
| `docs/superpowers/plans/2026-05-04-tech-debt-td3.md` | TD-3 plan |
