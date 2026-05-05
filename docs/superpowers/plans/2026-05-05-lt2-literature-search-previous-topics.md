# LT-2: Literature Search + Previous Topics — Implementation Plan

**Goal:** Implement LT-2 in the existing Streamlit UI: live literature search, Previous Topics, sidebar Connections, Knowledge Library polish, near-duplicate warnings, and connector request visibility.

**Scope decision:** Proceed in Streamlit. The failed Pre-LT-2 fixed-pane layout is not a blocker for LT-2. Full UI shell rearchitecture is deferred post-LT-3 unless Streamlit prevents capability testing.

**Baseline:** 262 automated tests after removing failed fixed-pane bridge tests.

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

### Task 1 — Schema + Literature Client

- [ ] Add `LiteratureSearch` ORM model.
- [ ] Add `LiteratureSearchClient.search(query)` with mocked-test coverage.
- [ ] Parse PubMed ESearch/EFetch responses.
- [ ] Parse Semantic Scholar search responses.
- [ ] Deduplicate by DOI.
- [ ] Gracefully skip timed-out/erroring sources.
- [ ] Log one `literature_searches` row per search.

### Task 2 — Wire NeuroTutorAgent Search

- [ ] Replace `_STARTER_LITERATURE` execution path with `LiteratureSearchClient`.
- [ ] Preserve normalized JSON result contract.
- [ ] Keep source queuing behavior unchanged.
- [ ] Update tests so common LTP/plasticity queries no longer assert starter-only behavior.

### Task 3 — Previous Topics

- [ ] Add `SessionManager.get_most_recent_context(engine)`.
- [ ] Add sidebar session list with 10 most recent sessions.
- [ ] Add load-on-demand behavior.
- [ ] Autosave current session before switching when user turns >= 3.
- [ ] Add editable topic labels.

### Task 4 — Connections Sidebar

- [ ] Show `NCBI_API_KEY` and `SEMANTIC_SCHOLAR_API_KEY` present/not-set indicators.
- [ ] Show pending connector request count from `source_suggestions`.
- [ ] Keep section collapsed by default.

### Task 5 — Knowledge Library Polish + Dedup

- [ ] Make pending cards show title, source type, topic context, DOI and URL clearly.
- [ ] Render DOI/URL as clickable links.
- [ ] Move approved summaries into an expander.
- [ ] Add env-driven near-duplicate threshold.
- [ ] Show warning without blocking approval.

### Task 6 — Suggestions Organization

- [ ] Rename/structure Suggestions sections as Dataset Import Requests and Connector Requests.
- [ ] Ensure connector request rows are clearly separated from import queue rows.

### Task 7 — Docs, Regression, Manual Test Readiness

- [ ] Update `.env.example` if present.
- [ ] Update `docs/projectStatus.md` with final test count.
- [ ] Run focused tests as each task lands.
- [ ] Run full `uv run pytest`.
- [ ] Start Streamlit for manual testing.

---

## Rollback / Stop Criteria

- If external APIs are unstable, keep mocked tests authoritative and make live calls degrade gracefully.
- If Previous Topics UI becomes too complex in Streamlit, ship a simpler selectbox/list version rather than reworking the shell.
- Do not reopen the fixed-pane layout problem during LT-2 unless it prevents capability testing.
