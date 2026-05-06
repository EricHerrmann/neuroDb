# LT-3: Research Agent Scaffolding — Manual Test Plan

**Feature:** Neuro-Research mode, research artifacts, knowledge growth metrics, hypothesis drafts
**Status:** Ready for manual execution — LT-3 implementation complete
**Spec:** `docs/superpowers/specs/2026-05-06-lt3-research-agent-scaffolding.md`
**Date:** 2026-05-06

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. `.env` has `ANTHROPIC_API_KEY` set. `NCBI_API_KEY` and `SEMANTIC_SCHOLAR_API_KEY` are optional.
2. Automated tests pass before manual testing:

```bash
uv run pytest tests/ -q --tb=no
```

Expected after LT-3 implementation: 307 tests pass.

3. Start the app:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

4. Open `http://localhost:8501` in a browser.

---

## T1 — Neuro-Research mode is available and persists

1. Open the Agent section in the sidebar.
2. Select **Neuro-Research**.
3. Stop and restart Streamlit.
4. **Pass:** The app reopens with **Neuro-Research** selected.
5. **Fail:** The app falls back to another mode after restart.

---

## T2 — Research agent uses the actual current date

1. In Neuro-Research mode, ask: `Summarize today's research context and record a research question about LTP and learning.`
2. Ask the agent what date it used for the saved artifact.
3. **Pass:** The saved artifact or response uses the actual test date from the running app, not an unrelated historical date.
4. **Fail:** The agent invents or uses an incorrect date.

---

## T3 — Knowledge growth metrics render and snapshot

1. Open the Research workspace tab.
2. Review the metrics summary.
3. Click the snapshot action.
4. Stop the Streamlit server, then run:

```bash
uv run python -c "import duckdb; conn = duckdb.connect('neurodb.duckdb', read_only=True); print(conn.execute('select snapshot_at, approved_sources_count, chat_sessions_count, literature_searches_count from knowledge_growth_snapshots order by id desc limit 1').fetchall())"
```

5. **Pass:** The Research tab shows metrics, and the query returns a recent snapshot row with numeric counts.
6. **Fail:** Metrics are missing, misleading, or no snapshot row is written.

---

## T4 — Research question is persisted

1. In Neuro-Research mode, ask: `Record this research question: How might hippocampal LTP mechanisms relate to measurable learning effects in available datasets?`
2. Open the Research workspace tab.
3. **Pass:** The question appears with status `open` or equivalent.
4. **Fail:** The question is absent after refresh or is only present in chat text.

---

## T5 — Dataset cross-reference is grounded

1. Ask: `Cross-reference local datasets that might be relevant to hippocampal plasticity, LTP, or learning.`
2. **Pass:** The agent uses local DB or semantic-search tools, returns dataset candidates or says none were found, and does not fabricate dataset IDs.
3. **Fail:** The agent answers only from training knowledge or invents local dataset details.

---

## T6 — Draft hypothesis includes required safeguards

1. Ask: `Draft a hypothesis linking hippocampal synaptic plasticity to learning-related dataset measures, including evidence, predictions, candidate datasets, confounds, and limitations.`
2. Open the Research workspace tab.
3. **Pass:** A draft hypothesis appears and includes evidence, predictions, candidate datasets if found, confounds, and limitations.
4. **Fail:** The draft omits confounds/limitations or presents an untested hypothesis as proven.

---

## T7 — Research mode does not mutate study notes implicitly

1. Before the test, note the number of study notes:

```bash
uv run python -c "import duckdb; conn = duckdb.connect('neurodb.duckdb', read_only=True); print(conn.execute('select count(*) from study_notes').fetchall())"
```

2. Restart Streamlit and ask Neuro-Research to draft a hypothesis from local datasets.
3. Stop Streamlit and rerun the count command.
4. **Pass:** The study-note count does not change unless the user explicitly used a non-research tagging workflow.
5. **Fail:** Research mode silently creates or modifies study notes.

---

## T8 — Existing modes still work

1. Switch to **Local DB** and ask for a dataset count.
2. Switch to **External DB** and ask for an external dataset search.
3. Switch to **Neuro-Tutor** and ask for a literature search about hippocampal LTP.
4. **Pass:** All three existing modes instantiate and use their expected tools.
5. **Fail:** Adding Neuro-Research breaks existing mode behavior.

---

## Sign-off

| Test | Result | Notes |
|------|--------|-------|
| T1 | Not run | |
| T2 | Not run | |
| T3 | Not run | |
| T4 | Not run | |
| T5 | Not run | |
| T6 | Not run | |
| T7 | Not run | |
| T8 | Not run | |

**Signed off by:**  **Date:**
