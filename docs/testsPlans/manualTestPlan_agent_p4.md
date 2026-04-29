# Agent P4 Manual Test Plan — Context Persistence

**Status:** Signed off (with bug fix — see Test 5 note)
**Tester:** Eric Herrmann
**Scope:** Session lifecycle, prior-context injection, session summary generation, cross-session memory
**Date:** <!-- fill in on execution -->

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

```bash
git status        # confirm on main, clean working tree
uv sync
uv run pytest tests/ -v   # all tests must pass before starting
grep ANTHROPIC_API_KEY .env   # must return a non-empty value
```

Ensure data is ingested and at least one study tag exists:
```bash
uv run scripts/ingest.py --source dandi --limit 10
uv run scripts/study.py tag --source dandi --id 000003 --concept "hippocampus place cells"
```

```bash
uv run streamlit run src/neurodb/ui/app.py
```

Open `http://localhost:8501`.

---

## Test 1 — Session start UI visible

| # | Step | Expected |
|---|------|----------|
| 1.1 | Open sidebar | Topic input and "Start Session" button visible above chat history |
| 1.2 | No active session | Chat input disabled or hidden until session started |

---

## Test 2 — Cold start (no prior context)

| # | Step | Expected |
|---|------|----------|
| 2.1 | Type a topic (e.g. "hippocampus") and click Start Session | Session starts; no prior context block shown (first session) |
| 2.2 | Ask a question in chat | Agent responds normally |
| 2.3 | Click "End Session" | Success message; session summary stored |

---

## Test 3 — Session summary stored in ChromaDB

After completing Test 2:
```bash
# Confirm agent_context collection exists in ChromaDB
ls neurodb_chroma/
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | `neurodb_chroma/` directory exists | ChromaDB persists across restarts |
| 3.2 | No error in terminal during End Session | Summary generated and stored without exception |

---

## Test 4 — Prior context injected on second session

Start a second session with the same or related topic:

| # | Step | Expected |
|---|------|----------|
| 4.1 | Enter topic "hippocampus" and click Start Session | Prior context block shown (from Test 2 session) |
| 4.2 | Prior session summary visible in sidebar or chat intro | References concepts/datasets from the previous session |
| 4.3 | Ask a question; agent references prior session | Agent response aware of previous session's content |

---

## Test 5 — Unrelated topic gets no prior context

| # | Step | Expected |
|---|------|----------|
| 5.1 | Start session with unrelated topic (e.g. "motor cortex") | No prior hippocampus context injected |
| 5.2 | Agent has no knowledge of prior hippocampus session | Agent responds as if fresh on this topic |

**Bug found (2026-04-29):** Music → emotion injected prior context. Root cause: `get_relevant()` returned nearest neighbors with no distance threshold, so any stored summary was returned regardless of similarity. Fix: cosine-distance threshold of 0.5 added to `AgentContextStore.get_relevant()` in `session_manager.py`. Two tests added covering the filter. Re-test passed after fix.

---

## Test 6 — End session without sending any messages

| # | Step | Expected |
|---|------|----------|
| 6.1 | Start session, immediately click End Session | No error; no summary stored (empty conversation) |

---

## Test 7 — Session summary survives server restart

| # | Step | Expected |
|---|------|----------|
| 7.1 | Stop and restart Streamlit | No re-embedding on startup |
| 7.2 | Start session with topic from Test 2 | Prior context still available; ChromaDB persisted correctly |

---

## Pass Criteria

- [x] `uv run pytest tests/ -v` — all tests pass (121)
- [x] Topic input and Start Session button visible in sidebar
- [x] Cold start shows no prior context (correct)
- [x] End Session generates and stores summary without error
- [x] Second session with matching topic shows injected prior context
- [x] Unrelated topic receives no irrelevant prior context (bug fixed — distance threshold added)
- [x] Empty session ends cleanly without storing a summary
- [x] Context persists across server restarts

**Sign-off:** Eric Herrmann Date: 2026-04-29
