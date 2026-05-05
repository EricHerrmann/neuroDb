# LT-2: Literature Search + Previous Topics — Implementation Plan

**Goal:** Implement LT-2 in the existing Streamlit UI: live literature search, Previous Topics, sidebar Connections, Knowledge Library polish, near-duplicate warnings, and connector request visibility.

**Scope decision:** Proceed in Streamlit. The failed Pre-LT-2 fixed-pane layout is not a blocker for LT-2. Full UI shell rearchitecture is deferred post-LT-3 unless Streamlit prevents capability testing.

**Current test count:** 274 after Tasks 1-6.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Create | `src/neurodb/literature_client.py` | PubMed + Semantic Scholar search, DOI dedup, logging |
| Modify | `src/neurodb/schema.py` | Add `LiteratureSearch` table |
| Modify | `src/neurodb/agents/tutor_agent.py` | Replace starter `search_literature` stub |
| Modify | `src/neurodb/session_manager.py` | Add most-recent context lookup |
| Modify | `src/neurodb/ui/sidebar.py` | Add Previous Topics and Connections sections |
| Modify | `src/neurodb/ui/pages/chat.py` | Load selected previous context and autosave before switch |
| Modify | `src/neurodb/ui/pages/knowledge_library.py` | Card polish and near-duplicate warning |
| Modify | `src/neurodb/ui/pages/suggestions.py` | Separate dataset imports from connector requests |
| Modify | `.env.example` | Add optional LT-2 keys/settings if file exists |
| Create/Modify | `tests/unit/*`, `tests/integration/*` | Focused TDD coverage |

---

## Tasks

### Task 1 — Schema + Literature Client ✅ COMPLETE

- [x] Add `LiteratureSearch` ORM model.
- [x] Add `LiteratureSearchClient.search(query)` with mocked-test coverage.
- [x] Parse PubMed ESearch/EFetch responses.
- [x] Parse Semantic Scholar search responses.
- [x] Deduplicate by DOI.
- [x] Gracefully skip timed-out/erroring sources.
- [x] Log one `literature_searches` row per search.

### Task 2 — Wire NeuroTutorAgent Search ✅ COMPLETE

- [x] Replace `_STARTER_LITERATURE` execution path with `LiteratureSearchClient`.
- [x] Preserve normalized JSON result contract.
- [x] Keep source queuing behavior unchanged.
- [x] Update tests so common LTP/plasticity queries no longer assert starter-only behavior.

### Task 3 — Previous Topics ✅ COMPLETE

- [x] Add `SessionManager.get_most_recent_context(engine)`.
- [x] Add sidebar session list with 10 most recent sessions.
- [x] Add load-on-demand behavior.
- [x] Autosave current session before switching when user turns >= 3.
- [x] Add editable topic labels.

### Task 4 — Connections Sidebar ✅ COMPLETE

- [x] Show `NCBI_API_KEY` and `SEMANTIC_SCHOLAR_API_KEY` present/not-set indicators.
- [x] Show pending connector request count from `source_suggestions`.
- [x] Keep section collapsed by default.

### Task 5 — Knowledge Library Polish + Dedup ✅ COMPLETE

- [x] Make pending cards show title, source type, topic context, DOI and URL clearly.
- [x] Render DOI/URL as clickable links.
- [x] Move approved summaries into an expander.
- [x] Add env-driven near-duplicate threshold.
- [x] Show warning without blocking approval.

### Task 6 — Suggestions Organization ✅ COMPLETE

- [x] Rename/structure Suggestions sections as Dataset Import Requests and Connector Requests.
- [x] Ensure connector request rows are clearly separated from import queue rows.

### Task 7 — Docs, Regression, Manual Test Readiness ✅ COMPLETE THROUGH REGRESSION

- [x] Update `.env.example` if present. No `.env.example` exists in this repo.
- [x] Update `docs/projectStatus.md` with final test count.
- [x] Run focused tests as each task lands.
- [x] Run full `uv run pytest`.
- [x] Start Streamlit for manual testing.

---

## Rollback / Stop Criteria

- If external APIs are unstable, keep mocked tests authoritative and make live calls degrade gracefully.
- If Previous Topics UI becomes too complex in Streamlit, ship a simpler selectbox/list version rather than reworking the shell.
- Do not reopen the fixed-pane layout problem during LT-2 unless it prevents capability testing.
