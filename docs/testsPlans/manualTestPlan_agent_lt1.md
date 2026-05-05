# Agent LT-1 Manual Test Plan — Neuro-Tutor Foundation

**Status:** Signed off — LT-1 complete
**Tester:** Eric Herrmann
**Scope:** BaseAgent migration, Local DB / External DB / Neuro-Tutor mode wiring, auto-session behavior, Knowledge Library queue and approval flow, compatibility-shim cleanup gate
**Date:** 2026-05-05

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

Use a disposable LT-1 test database so the checks below do not depend on or alter the main working DB:

```bash
git status
uv sync
grep ANTHROPIC_API_KEY .env
```

Use this disposable DB filename for all commands below:

```bash
neurodb_lt1_manual.duckdb
```

Seed minimal local data before starting Streamlit:

```bash
uv run scripts/ingest.py --source openneuro --limit 5 --db neurodb_lt1_manual.duckdb
uv run scripts/ingest.py --source dandi --limit 5 --db neurodb_lt1_manual.duckdb
```

## Automated Test Gate

Before running the manual checks, run the automated LT-1 verification suite selected by the implementation plan:

```bash
uv run pytest --tb=short -q
```

Expected: the command exits successfully and all tests pass.

Start the app with the disposable DB:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb_lt1_manual.duckdb
```

Open `http://localhost:8501`.

> Restart note: if Streamlit was already running before the LT-1 changes, stop it and start a fresh server.

---

## Test 1 — LT-1 UI shell and mode labels render

| # | Step | Expected |
|---|------|----------|
| 1.1 | Open the app | App loads without import, schema, or Chroma initialization errors |
| 1.2 | Inspect the chat/workspace layout | Chat remains the primary left pane; workspace tabs remain on the right |
| 1.3 | Inspect the mode control | Three labels are visible: `Local DB`, `External DB`, `Neuro-Tutor` |
| 1.4 | Inspect removed session controls | No `Start Session`, `End Session`, topic input, or relevance-threshold slider is visible |
| 1.5 | Inspect right workspace tabs | `Knowledge Library` is visible alongside the existing workspace tabs |

---

## Test 2 — Local DB mode preserves existing database-agent behavior

Set mode to `Local DB`.

Ask:

```text
How many OpenNeuro datasets are currently in this database?
```

| # | Step | Expected |
|---|------|----------|
| 2.1 | Submit the question | Agent responds without streaming or tool-dispatch errors |
| 2.2 | Observe agent activity | Activity includes local database work such as `query_db` |
| 2.3 | Review the answer | Answer is grounded in the disposable DB and does not claim to search external dataset repositories |
| 2.4 | Check chat history after completion | User question and assistant answer remain visible |

---

## Test 3 — External DB mode preserves discovery behavior

Set mode to `External DB`.

Ask:

```text
Search OpenNeuro for retinotopy datasets and suggest one relevant to visual plasticity.
```

If the agent asks for confirmation, reply:

```text
yes
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | Submit the discovery request | Agent responds without error |
| 3.2 | Observe agent activity | Activity includes discovery work such as `search_external` |
| 3.3 | Confirm a candidate if prompted | Follow-up response works in the same conversation |
| 3.4 | Open `Suggestions` | A pending import suggestion appears when the agent queued one |
| 3.5 | Inspect the suggestion | Title/source/reasoning are coherent and tied to the request |

---

## Test 4 — Neuro-Tutor queues a source for curation

Set mode to `Neuro-Tutor`.

Ask:

```text
Recommend one classic paper or textbook source for learning long-term potentiation and queue it for my Knowledge Library.
```

| # | Step | Expected |
|---|------|----------|
| 4.1 | Submit the Neuro-Tutor prompt | Agent responds without DB-agent mode errors |
| 4.2 | Observe agent activity | Activity includes `queue_source`; `search_external` is not used |
| 4.3 | Open `Knowledge Library` | A pending source is visible |
| 4.4 | Inspect the pending row | Row includes title, source type, topic context, and queued date |
| 4.5 | Repeat a prompt that queues the same source, if practical | Duplicate is not added as a second pending source |

---

## Test 5 — Knowledge Library approve/reject flow

Use pending items created in Test 4.

| # | Step | Expected |
|---|------|----------|
| 5.1 | Click `Approve` on one pending source | Spinner appears while summary is generated |
| 5.2 | Approval completes | Source leaves Pending and appears in Library |
| 5.3 | Expand or inspect the approved source | Summary preview/full summary is visible |
| 5.4 | Ask Neuro-Tutor a follow-up about the approved source's topic | Activity includes `search_knowledge_library` or answer reflects approved library context |
| 5.5 | Queue or use another pending source and click `Reject` | Source leaves Pending and does not appear in Library |

Expected behavior: approval writes both structured metadata and an embedded summary; rejection only changes review status.

---

## Test 6 — Auto-session threshold and Clear behavior

LT-1 does not include a UI for completed sessions. Verify completed chat-session rows from the command line using the query below.

In any mode, start a fresh conversation with fewer than three user turns.

| # | Step | Expected |
|---|------|----------|
| 6.1 | Send one or two user messages | Conversation works normally |
| 6.2 | Click `Clear` | Chat clears without visible summary-generation spinner |
| 6.3 | Run the command-line verification query below | No new `chat_sessions` row is added for the short conversation |

Now start a fresh Neuro-Tutor conversation with three user turns:

```text
What is synaptic plasticity?
How is LTP different from LTD?
What should I study next?
```

Then click `Clear`.

| # | Step | Expected |
|---|------|----------|
| 6.4 | Click `Clear` after three user turns | Session summary is generated and chat clears |
| 6.5 | Run the command-line verification query below | A new row appears with mode `neuro_tutor`, message count `3`, and a non-empty summary preview |
| 6.6 | Start a new related conversation | Prior context can be retrieved silently; no explicit prior-context system message appears in chat |

Verification query:

```bash
uv run scripts/query_cli.py --db neurodb_lt1_manual.duckdb --sql "SELECT agent_mode, message_count, summary_preview FROM chat_sessions ORDER BY id DESC LIMIT 3;"
```

---

## Test 7 — Mode switching preserves conversation and resets only local chapter context

| # | Step | Expected |
|---|------|----------|
| 7.1 | Start in `Local DB`, ask a database question | Response completes and remains in chat history |
| 7.2 | Switch to `Neuro-Tutor` | App reruns without clearing visible conversation |
| 7.3 | Ask a tutor follow-up | Agent responds using Neuro-Tutor tools |
| 7.4 | Switch back to `Local DB` | Conversation remains visible |
| 7.5 | If chapter context was set before switching to Neuro-Tutor | Chapter context is cleared for Neuro-Tutor and can be set again in Local DB |

---

## Test 8 — Compatibility-shim cleanup gate

This test is run after Tests 1-7 pass and before LT-1 is marked complete.

| # | Step | Expected |
|---|------|----------|
| 8.1 | Confirm `src/neurodb/agent.py` exists during LT-1 manual testing | Legacy import shim is present |
| 8.2 | Run the implementation-plan cleanup search | Only the compatibility test imports `neurodb.agent` |
| 8.3 | Remove the shim according to Task 9 | `src/neurodb/agent.py` and `tests/unit/test_agent_compat.py` are deleted |
| 8.4 | Rerun automated tests | Full suite passes |
| 8.5 | Restart Streamlit and smoke-test app load | App still starts without legacy import errors |

Cleanup search:

```bash
rg -n "from neurodb\\.agent|import neurodb\\.agent" src scripts tests
```

---

## Pass Criteria

- [x] Full automated suite passes before manual testing
- [x] Streamlit starts against `neurodb_lt1_manual.duckdb`
- [x] Local DB mode works and uses local database tools
- [x] External DB mode works and uses discovery tools
- [x] Neuro-Tutor mode works and does not use dataset-discovery tools
- [x] Neuro-Tutor queues at least one source into Knowledge Library Pending
- [x] Approve creates an approved library entry with a summary
- [x] Reject removes a pending source from the Pending list without approving it
- [x] Clear does not summarize conversations with fewer than three user turns
- [x] Clear summarizes conversations with at least three user turns and writes a `chat_sessions` row
- [x] Mode switching does not clear visible chat history
- [x] Compatibility shim remained during manual testing and was removed only after Tests 1-7 passed
- [x] Post-cleanup automated suite passes: `255 passed, 2 warnings`
- [x] Post-cleanup Streamlit restart smoke check passes

## Manual Test Result

Tests 1-7 passed by user approval on 2026-05-05. Test 8 cleanup gate passed: the temporary `neurodb.agent` shim and compatibility test were removed, no legacy imports remain, the full suite passed, and Streamlit restarted successfully.

**Sign-off:** Eric Herrmann Date: 2026-05-05
