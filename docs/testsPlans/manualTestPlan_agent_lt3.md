# LT-3: Research Agent Scaffolding — Manual Test Plan

**Feature:** Neuro-Research mode, research artifacts, knowledge growth metrics, hypothesis drafts
**Status:** Passed — signed off 2026-05-06
**Spec:** `docs/superpowers/specs/2026-05-06-lt3-research-agent-scaffolding.md`
**Date:** 2026-05-06

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. `.env` has `ANTHROPIC_API_KEY` set. `NCBI_API_KEY` and `SEMANTIC_SCHOLAR_API_KEY` are optional.
   `NEURODB_RESEARCH_MAX_TOOL_ITERATIONS` controls the Neuro-Research per-turn tool budget; current manual re-test value is `40`.
2. Automated tests pass before manual testing:

```bash
uv run pytest tests/ -q --tb=no
```

Expected after LT-3 T6/T7 remediation: 319 tests pass.

3. Start the app:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

4. Open `http://localhost:8501` in a browser.

---

## Run Summary — 2026-05-06

| Test | Result | Log IDs | Notes |
|------|--------|---------|-------|
| T1 | Pass | LOG-029 | Neuro-Research mode is available and persists |
| T2 | Pass | LOG-030 | Agent used the correct current date and knew prior context; minor header/title font-size issue noted |
| T3 | Pass | LOG-031 | Knowledge-growth metrics rendered and snapshot flow passed |
| T4 | Pass | LOG-032 | Research question persisted |
| T5 | Pass | LOG-033 | Dataset cross-reference was grounded |
| T6 | Pass | LOG-034, LOG-035, LOG-038 | Draft hypothesis workflow passed after max-turn/tool-result remediation |
| T7 | Pass | LOG-036, LOG-039 | Research mode did not mutate study notes implicitly |
| T8 | Pass | LOG-036 | Existing Local DB, External DB, and Neuro-Tutor modes still worked after LT-3 remediation |

## LT-3 Issues Summary

| Log ID | Test | Issue | Impact | Current status |
|--------|------|-------|--------|----------------|
| LOG-030 | T2 | Titles/headers render too large | Minor UI polish issue; does not block T2 correctness | Open |
| LOG-034 | T6 | Agent reached maximum tool iterations during grounded hypothesis drafting; retry produced Anthropic 400 due to `tool_use` without immediately following `tool_result` | Blocks hypothesis drafting sign-off and exposes tool-loop recovery bug | Resolved — T6 passed |
| LOG-035 | T6 | T6 still fails with max-turns issue after clearing context before running the test | Shows the problem is not only prior-context size | Resolved — T6 passed |
| LOG-036 | T7/T8 | T7 failed with max-turns error after local DB retrieval; T8 deferred | Blocks no-study-note-mutation verification and existing-mode regression check | Resolved — T7/T8 passed |
| LOG-037 | T6 | Research pane shows several research questions, but there is no way to delete or use them | Limits Research workspace usefulness and makes accumulated questions hard to manage | Open |

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
2. Watch the Agent activity panel while tools run.
3. **Pass:** Agent activity shows visible tool progress with a research budget, e.g. `Step N/40` when `.env` sets `NEURODB_RESEARCH_MAX_TOOL_ITERATIONS=40`.
4. Open the Research workspace tab.
5. **Pass:** A draft hypothesis appears and includes evidence, predictions, candidate datasets if found, confounds, and limitations.
6. **Observe:** Research questions may accumulate in the Research pane. Current known gap: no delete/use action exists for those questions (LOG-037).
7. **Pass:** If the agent still reaches the maximum tool-iteration budget, the app surfaces a clear budget message, saves compact partial research progress to valid API history, and a retry can continue from that saved progress without producing an Anthropic `tool_use` / `tool_result` ordering error.
8. **Fail:** The draft omits confounds/limitations, presents an untested hypothesis as proven, reaches max tool iterations without a clear budget message, loses the gathered partial progress, or a retry produces the Anthropic `tool_use` / `tool_result` ordering error.

---

## T7 — Research mode does not mutate study notes implicitly

1. Before the test, note the number of study notes:

```bash
uv run python -c "import duckdb; conn = duckdb.connect('neurodb.duckdb', read_only=True); print(conn.execute('select count(*) from study_notes').fetchall())"
```

2. Restart Streamlit and ask Neuro-Research to draft a hypothesis from local datasets.
3. Watch the Agent activity panel while tools run.
4. **Pass:** Agent activity shows visible tool progress with a research budget, e.g. `Step N/40` when `.env` sets `NEURODB_RESEARCH_MAX_TOOL_ITERATIONS=40`.
5. Stop Streamlit and rerun the count command.
6. **Pass:** The study-note count does not change unless the user explicitly used a non-research tagging workflow.
7. **Pass:** If the agent reaches the maximum tool-iteration budget, the app surfaces a clear budget message, saves compact partial research progress to valid API history, and a retry can continue from that saved progress without producing an Anthropic `tool_use` / `tool_result` ordering error.
8. **Fail:** Research mode silently creates/modifies study notes, reaches max tool iterations without a clear budget message, loses gathered partial progress, or a retry produces the Anthropic `tool_use` / `tool_result` ordering error.

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
| T1 | Pass | LOG-029 |
| T2 | Pass | LOG-030 — correct date/context; header font too large |
| T3 | Pass | LOG-031 |
| T4 | Pass | LOG-032 |
| T5 | Pass | LOG-033 |
| T6 | Pass | LOG-034, LOG-035, LOG-038 — max-turn/tool-result remediation verified; LOG-037 remains non-blocking |
| T7 | Pass | LOG-036, LOG-039 — no implicit study-note mutation |
| T8 | Pass | Existing modes still work |

**Signed off by:** User  **Date:** 2026-05-06
