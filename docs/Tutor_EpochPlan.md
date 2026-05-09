# NeuroDb — Tutor Epoch Plan

**Status:** MVP complete (LT-1/2/3 signed off)
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/tutor/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Give the user a capable neuroscience learning partner that remembers what has been explored and builds on it, so learning compounds over time.

**Active work:** None — MVP complete. Open backlog items are deferred until a dedicated Tutor backlog sprint.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| LT-1 | NeuroTutorAgent, Knowledge Library storage + UI, auto-session | Complete | — | 2026-05-05 | — |
| LT-2 | Live PubMed + Semantic Scholar search, Previous Topics panel, semantic dedup | Complete | — | 2026-05-06 | — |
| LT-3 | Research agent scaffolding (Tutor as foundation) | Complete | — | 2026-05-06 | — |

Active test plan: none

---

## Open Backlog

| Log ID | Issue |
|--------|-------|
| LOG-001 | Textbook dropdown appears pre-selected without explicit user action |
| LOG-006 | User cannot tell which agent/LLM/model is active — deferred post-LT-3 |
| LOG-030 | LT-3 T2 passed but titles/headers render too large |
| LOG-041 | No UI path to view generated session summary |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-05 | Separate NeuroTutorAgent class, not a third mode on NeuroDbAgent | RAG-first retrieval strategy is fundamentally different from tool-first DB agent; separate classes enforce the boundary and allow independent evolution |
| 2026-05-05 | Knowledge library: DuckDB table + ChromaDB collection | `knowledge_sources` handles structured metadata, status, and dedup; `knowledge_library` ChromaDB handles semantic indexing and retrieval |
| 2026-05-05 | Sessions table built in LT-1, Previous Topics UI deferred to LT-2 | Data needs to accumulate before the browsing UI is useful |
| 2026-05-05 | Minimum 3 user turns to store a session | Short conversations produce low-quality summaries that pollute the Previous Topics list |

---

## Owned Storage

| Store | Name | Purpose |
|-------|------|---------|
| DuckDB | `knowledge_sources` | Pending queue, approval status, summaries, chroma IDs |
| ChromaDB | `knowledge_library` | Approved summaries, semantically indexed |
| ChromaDB | `agent_context` | Session summaries for cross-session memory |
