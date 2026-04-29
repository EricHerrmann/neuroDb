# Agent P4 Manual Test Plan — Context Persistence

**Status:** Pending
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

- [ ] `uv run pytest tests/ -v` — all tests pass
- [ ] Topic input and Start Session button visible in sidebar
- [ ] Cold start shows no prior context (correct)
- [ ] End Session generates and stores summary without error
- [ ] Second session with matching topic shows injected prior context
- [ ] Unrelated topic receives no irrelevant prior context
- [ ] Empty session ends cleanly without storing a summary
- [ ] Context persists across server restarts

**Sign-off:** _________________________________ Date: _____________
