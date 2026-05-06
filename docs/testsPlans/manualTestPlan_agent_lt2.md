# LT-2: Literature Search + Previous Topics — Manual Test Plan

**Feature:** Live literature search, Previous Topics, sidebar Connections, Knowledge Library polish, connector request visibility
**Status:** Signed off — 2026-05-06
**Spec:** `docs/superpowers/specs/2026-05-05-lt2-literature-search-previous-topics.md`
**Date:** 2026-05-05

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Run Summary — 2026-05-06

| Test | Result | Log IDs | Notes |
|------|--------|---------|-------|
| T1 | Pass | LOG-015 | Live results returned; agent wrote incorrect session date (Jan 27 instead of May 4) |
| T2 | Pass | — | Search log row written; server must be stopped first due to DuckDB exclusive lock |
| T3 | Pass | LOG-016, LOG-018 resolved | Root cause fixed; re-run confirmed pass — agent recalled prior session |
| T4 | Pass | LOG-019 resolved | Root cause fixed; re-run confirmed pass — ▸ indicator and context caption visible |
| T5 | Pass | — | Edited topic label persists after refresh |
| T6 | Pass | LOG-017 resolved | IndentationError fixed; re-run confirmed pass |
| T7 | Pass | — | |
| T8 | Pass | — | |
| T9 | Pass | — | Dataset imports and connector requests correctly separated |

**Additional issues logged during this run (not tied to a specific test):**

| Log ID | Issue | Impact |
|--------|-------|--------|
| LOG-014 | Semantic Scholar does not issue API keys to non-academic accounts | Architecture and connector setup docs need updating |
| LOG-021 | Agent mode selection does not persist across sessions | UX friction; user must re-select mode on every restart |

---

## Prerequisites

1. `.env` has `ANTHROPIC_API_KEY` set. `NCBI_API_KEY` and `SEMANTIC_SCHOLAR_API_KEY` are optional.
2. Automated tests pass before manual testing:

```bash
uv run pytest tests/ -q --tb=no
```

Expected after LT-2 implementation: all tests pass.

3. Start the app:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

4. Open `http://localhost:8501` in a browser.

---

## T1 — Literature search returns live results

1. Switch to Neuro-Tutor mode.
2. Ask: `Find recent review papers about hippocampal long-term potentiation.`
3. **Pass:** The agent uses `search_literature`, returns candidate papers, and does not claim no literature exists when PubMed or Semantic Scholar is reachable.
4. **Fail:** The tool still returns only LT-1 starter sources or an empty stub for a common query.

---

## T2 — Literature search log row is written

1. After T1, **click Clear** in the chat panel to end the session before stopping the server.

   > Sessions are written to DuckDB when Clear is pressed. Stopping the server without clearing loses the session record and will cause T3/T4 to fail.

2. Stop the Streamlit server (`Ctrl+C`), then run:

```bash
uv run python -c "import duckdb; conn = duckdb.connect('neurodb.duckdb', read_only=True); print(conn.execute('select query, pubmed_count, semantic_scholar_count from literature_searches order by id desc limit 1').fetchall())"
```

> DuckDB holds an exclusive write lock while the app is running; no concurrent connections are possible. Stop the server before querying.

3. **Pass:** The command prints one row containing the query and numeric result counts.
4. **Fail:** The table is missing, the command errors, or the latest row is unrelated.
5. Restart the Streamlit server before continuing to T3.

---

## T3 — Previous Topics auto-loads most recent session

> Prerequisite: T2 must have ended with Clear pressed (≥3 turns). Sessions only auto-load if they were properly closed.

1. After restarting Streamlit (from T2 step 5), switch to the same agent mode used in T1.
2. Observe the Previous Topics sidebar: the recent session should appear.
3. Observe the top of the chat panel: a "Prior context: …" caption should appear if prior context was found.
4. Ask the agent: `What did we discuss in our last session?`
5. **Pass:** The sidebar shows the T1 session. The chat panel shows the prior context caption. The agent references the prior topic in its response.
6. **Fail:** The sidebar is empty, the caption is absent, or the agent has no knowledge of the prior session.

---

## T4 — Previous Topics load-on-demand

> Prerequisite: At least one completed session must exist (Clear was pressed during that session).

1. Open Previous Topics in the sidebar.
2. Select a session by clicking its button.
3. **Pass:** (a) The selected session button shows a `▸` prefix indicating it is active. (b) An "Active: …" caption appears at the top of the Previous Topics section. (c) A "Prior context: …" caption appears at the top of the chat panel. (d) The transcript clears and a new conversation can begin with the agent aware of the selected session.
4. **Fail:** No `▸` indicator appears, the captions are absent, or the agent has no knowledge of the selected session.

---

## T5 — Editable topic labels

1. Edit a Previous Topics label.
2. Press Enter or use the provided save affordance.
3. Refresh the app.
4. **Pass:** The edited label persists in the Previous Topics list.
5. **Fail:** The label reverts or the edit cannot be completed.

---

## T6 — Connections section shows API and connector status

1. Open Connections in the sidebar.
2. Inspect PubMed and Semantic Scholar status.
3. Add or confirm at least one pending connector request in Suggestions if available.
4. **Pass:** Key presence indicators match `.env`; pending connector request count matches Suggestions.
5. **Fail:** Indicators are missing, misleading, or connector counts do not match.

---

## T7 — Knowledge Library pending cards are verifiable

1. Queue a source with DOI or URL.
2. Open Knowledge Library → Pending.
3. **Pass:** Title, source type, topic context, and DOI/URL links are clearly visible without expanding hidden details.
4. **Fail:** Source identity is visually unclear or DOI/URL cannot be opened.

---

## T8 — Near-duplicate warning

1. Approve one source.
2. Queue a very similar pending source.
3. Open Knowledge Library → Pending.
4. **Pass:** A near-duplicate warning appears, but Approve remains available.
5. **Fail:** No warning appears for an obvious duplicate, or approval is blocked.

---

## T9 — Suggestions separates dataset imports and connector requests

1. Open Suggestions.
2. **Pass:** Dataset Import Requests and Connector Requests are visually separated with clear section headers.
3. **Fail:** Import requests and connector requests are mixed under one ambiguous list.

---

## Sign-off

| Test | Result | Notes |
|------|--------|-------|
| T1 | Pass | LOG-015: incorrect session date written |
| T2 | Pass | Stop server before querying (DuckDB lock) |
| T3 | Pass | Re-run confirmed |
| T4 | Pass | Re-run confirmed |
| T5 | Pass | |
| T6 | Pass | LOG-017 resolved |
| T7 | Pass | |
| T8 | Pass | |
| T9 | Pass | |

**Signed off by:** Eric Herrmann  **Date:** 2026-05-06
