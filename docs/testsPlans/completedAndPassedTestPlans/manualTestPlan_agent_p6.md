# Agent P6 Manual Test Plan — Learning Agent Features

**Status:** ✅ Signed off
**Tester:** Eric Herrmann
**Scope:** F1 embedding deduplication, F2 agent response streaming, F3 split-workspace UI
**Date:** 2026-05-04

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

Use a disposable P6 test database so the checks below do not depend on or alter the main working DB:

```bash
git status
uv sync
grep ANTHROPIC_API_KEY .env
```

## Automated Test Gate

Before running the manual checks below, run the automated P6 verification command exactly as shown:

```bash
uv run pytest tests/unit/test_embed_hooks.py tests/unit/test_agent.py tests/unit/test_session_manager.py tests/unit/test_chat_ui.py tests/unit/test_schema.py -q
```

Expected: the command exits successfully and all listed tests pass.

Use this disposable DB filename for the commands below:

```bash
neurodb_p6_manual.duckdb
```

> **Order requirement for F1:** Do **not** start Streamlit before Tests 1–2. Those tests use the CLI ingest path, which opens the same Chroma persistent directory as the app. Run the F1 ingest / re-ingest checks first while the app is stopped, then start Streamlit before Test 3.

---

## Test 1 — F1 initial ingest creates embedding state

Ensure Streamlit is **not** running against `neurodb_p6_manual.duckdb` for Tests 1–2.

Run a first ingest into the disposable DB:

```bash
uv run scripts/ingest.py --source openneuro --limit 5 --db neurodb_p6_manual.duckdb
```

Verify counts:

```bash
uv run scripts/query_cli.py --db neurodb_p6_manual.duckdb --sql "SELECT COUNT(*) FROM v_all_datasets WHERE source = 'openneuro';"
uv run scripts/query_cli.py --db neurodb_p6_manual.duckdb --sql "SELECT COUNT(*) FROM dataset_embedding_state WHERE source = 'openneuro';"
```

| # | Step | Expected |
|---|------|----------|
| 1.1 | First OpenNeuro ingest completes | Command exits without error |
| 1.2 | Ingest output prints embedding step | Terminal includes `Embedding datasets into vector store…` |
| 1.3 | First ingest embeds records | Terminal ends with `Embedded N dataset(s).` where `N > 0` |
| 1.4 | Query `v_all_datasets` for `openneuro` | Count is `> 0` |
| 1.5 | Query `dataset_embedding_state` for `openneuro` | Count matches the OpenNeuro dataset count |

---

## Test 2 — F1 repeat ingest skips unchanged embeddings

Keep Streamlit stopped. Run the same ingest command again with no source-data changes:

```bash
uv run scripts/ingest.py --source openneuro --limit 5 --db neurodb_p6_manual.duckdb
uv run scripts/query_cli.py --db neurodb_p6_manual.duckdb --sql "SELECT COUNT(*) FROM dataset_embedding_state WHERE source = 'openneuro';"
```

| # | Step | Expected |
|---|------|----------|
| 2.1 | Second OpenNeuro ingest completes | Command exits without error |
| 2.2 | Second ingest reaches embedding step | Terminal still includes `Embedding datasets into vector store…` |
| 2.3 | Unchanged datasets are skipped | Terminal ends with `Embedded 0 dataset(s).` |
| 2.4 | Embedding-state row count after rerun | Count is unchanged from Test 1 |

Expected behavior: a no-op re-ingest does not re-embed unchanged dataset text.

---

## Test 3 — Prepare remaining local data and start the app after F1 checks

After Tests 1–2 complete, seed DANDI data for the later learning/discovery UI checks:

```bash
uv run scripts/ingest.py --source dandi --limit 5 --db neurodb_p6_manual.duckdb
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | DANDI ingest completes | Command exits without error |
| 3.2 | DANDI ingest prints embedding step | Terminal includes `Embedding datasets into vector store…` |
| 3.3 | DANDI records are available for later UI checks | Command completes without DB/Chroma error |

Start the app with the same DB:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb_p6_manual.duckdb
```

Open `http://localhost:8501`.

> **Restart note:** If the Streamlit server was already running before the latest P6 changes, stop it and start a fresh server. `app.py`, `chat.py`, and `agent.py` should be tested from a full restart.

---

## Test 4 — F2 learning-mode response streams and shows visible activity

In the app:

| # | Step | Expected |
|---|------|----------|
| 4.1 | Open the app with the P6 DB | Main page shows chat as the primary left pane and workspace tabs on the right |
| 4.2 | Start a new session | Session starts without error |
| 4.3 | Confirm mode is `learning` | Agent mode control shows `learning` selected |
| 4.4 | Ask: `How many OpenNeuro datasets are currently in this database?` | Assistant begins responding without a blank hang |
| 4.5 | Observe the left chat pane while the answer is being generated | Partial assistant text appears progressively, or the activity area shows the agent working before the final response completes |
| 4.6 | Observe the activity area | Visible activity appears for tool work such as `query_db` rather than only a spinner |
| 4.7 | Final answer completes | Response is shown in full and remains in chat history |

---

## Test 5 — F2 discovery-mode streaming survives multi-turn confirmation

Set chapter context to `Ch12` before the discovery query if not already active.

Ask in chat:

```text
Search OpenNeuro for retinotopy datasets and suggest one relevant to Ch12.
```

If the agent proposes a candidate and asks for confirmation, reply:

```text
yes
```

| # | Step | Expected |
|---|------|----------|
| 5.1 | Switch mode to `discovery` | Mode updates without app error |
| 5.2 | Submit the discovery request | Agent begins responding without a silent hang |
| 5.3 | Observe the activity area during the request | Visible activity shows tool work such as `search_external` and any follow-on actions |
| 5.4 | Agent names a candidate and/or asks for confirmation | Response is coherent and tied to the discovery request |
| 5.5 | Reply `yes` in the same session | Agent responds normally; chat history remains visible |
| 5.6 | Open `Suggestions` in the right workspace pane | A pending import item appears for the selected dataset |

Expected behavior: multi-turn streaming does not clear chat history, and tool-use activity remains visible across turns.

---

## Test 6 — F3 split-workspace layout keeps chat primary

| # | Step | Expected |
|---|------|----------|
| 6.1 | Load the app on a normal desktop-width window | Main content is split into a left chat workspace and right utility workspace |
| 6.2 | Inspect the left pane | It contains the agent workspace, session controls, chat transcript, and message composer |
| 6.3 | Inspect the right pane | It contains tabs for `Suggestions`, `Study Log`, `Datasets`, `Registry`, and `SQL` |
| 6.4 | Inspect the sidebar | Sidebar shows lightweight workspace status only; chat is no longer confined to the sidebar |
| 6.5 | Switch among right-pane tabs | The left chat pane remains visible and the active session is preserved |

---

## Test 7 — F3 supporting actions work without leaving chat context

Use the same live session from Tests 5–6.

| # | Step | Expected |
|---|------|----------|
| 7.1 | In the right pane, open `Suggestions` and import a queued item if one exists | Import runs and shows success/error feedback in the right pane without collapsing the left chat workspace |
| 7.2 | After the import, look back at the left pane | Prior chat transcript is still present |
| 7.3 | Send a follow-up message such as `I imported that dataset.` | Agent responds normally; no history clear or empty-response glitch occurs |
| 7.4 | Open another right-pane tab such as `Datasets` or `Study Log` | Supporting view loads while the chat pane remains in place |

Expected behavior: supporting workflows are accessible without navigating away from the agent context.

---

## Pass Criteria

- [x] `uv run pytest tests/unit/test_embed_hooks.py tests/unit/test_agent.py tests/unit/test_session_manager.py tests/unit/test_chat_ui.py tests/unit/test_schema.py -q` passes
- [x] First OpenNeuro ingest into the P6 DB embeds `N > 0` datasets
- [x] `dataset_embedding_state` row count matches the number of embedded OpenNeuro datasets after the first ingest
- [x] A second unchanged OpenNeuro ingest reports `Embedded 0 dataset(s).`
- [x] Learning-mode chat shows progressive response output and visible agent activity instead of a silent wait
- [x] Discovery-mode chat shows visible tool activity and survives the multi-turn `yes` confirmation flow without clearing history
- [x] Suggestions created from discovery mode appear in the right-pane workspace
- [x] Split-workspace layout shows chat as the primary left pane and utility tabs on the right
- [x] Importing or browsing supporting views does not force navigation away from the active chat context

**Sign-off:** P6 F1, F2, and F3 passed per user sign-off after the final UI update. Date: 2026-05-04
