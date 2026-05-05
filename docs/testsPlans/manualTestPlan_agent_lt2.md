# LT-2: Literature Search + Previous Topics — Manual Test Plan

**Feature:** Live literature search, Previous Topics, sidebar Connections, Knowledge Library polish, connector request visibility
**Status:** Draft — must be run after LT-2 implementation
**Spec:** `docs/superpowers/specs/2026-05-05-lt2-literature-search-previous-topics.md`
**Date:** 2026-05-05

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

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

1. After T1, run:

```bash
uv run python -c "from neurodb.db import get_engine; from sqlalchemy import text; e=get_engine('duckdb:///neurodb.duckdb'); print(e.connect().execute(text('select query, pubmed_count, semantic_scholar_count from literature_searches order by id desc limit 1')).fetchall())"
```

2. **Pass:** The command prints one row containing the query and numeric result counts.
3. **Fail:** The table is missing, the command errors, or the latest row is unrelated.

---

## T3 — Previous Topics auto-loads most recent session

1. Complete and clear a chat session with at least 3 user turns.
2. Restart Streamlit.
3. Switch to the same agent mode.
4. **Pass:** The sidebar Previous Topics section shows the recent topic, and the agent has prior context before the first new message.
5. **Fail:** The topic is absent or prior context is only loaded after the first new message.

---

## T4 — Previous Topics load-on-demand

1. Open Previous Topics in the sidebar.
2. Select an older session.
3. **Pass:** The current transcript clears, selected prior context loads, and the sidebar indicates the selected topic.
4. **Fail:** The transcript remains mixed with the old conversation or selected context is not reflected.

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
| T1 | | |
| T2 | | |
| T3 | | |
| T4 | | |
| T5 | | |
| T6 | | |
| T7 | | |
| T8 | | |
| T9 | | |

**Signed off by:** ___  **Date:** ___
