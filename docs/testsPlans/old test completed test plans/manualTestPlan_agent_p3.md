# Agent P3 Manual Test Plan — AI Agent Interface

**Status:** ✅ Signed off 2026-04-27
**Tester:** Eric Herrmann
**Scope:** Claude API agent tools, Agent Chat Streamlit tab, grounded answers
**Date:** 2026-04-27

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

```bash
git status        # confirm on main, clean working tree
uv sync
uv run pytest tests/ -v   # all tests must pass before starting
```

Ensure data is ingested and at least one study tag exists:
```bash
uv run scripts/ingest.py --source dandi --limit 10
uv run scripts/study.py tag --source dandi --id 000003 --concept "hippocampus place cells"
```

The `ANTHROPIC_API_KEY` must be present in `.env` at the repo root.
The Streamlit app loads it automatically via `python-dotenv` on startup.
```bash
grep ANTHROPIC_API_KEY .env   # must return a non-empty value
```

---

## Test 1 — Agent Chat tab visible in UI

```bash
uv run streamlit run src/neurodb/ui/app.py
```

Open `http://localhost:8501`.

| # | Step | Expected |
|---|------|----------|
| 1.1 | Sidebar shows four nav options | Dataset Browser, SQL Query, Study Log, Agent Chat |
| 1.2 | Navigate to Agent Chat | Page loads without error |
| 1.3 | Chat input box visible | Text input at bottom of page |

---

## Test 2 — Agent answers a dataset question (grounded)

In Agent Chat, type:
```
How many DANDI datasets are in the database?
```

| # | Step | Expected |
|---|------|----------|
| 2.1 | Agent responds without error | No exception or API error shown |
| 2.2 | Answer references a real count | Number matches `SELECT COUNT(*) FROM dandi_datasets` |
| 2.3 | Response does not fabricate dataset IDs | Any IDs cited exist in `datasets_index` |

---

## Test 3 — Agent uses semantic search tool

In Agent Chat, type:
```
Find datasets related to spatial navigation
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | Agent calls semantic_search tool | Tool use visible in response or terminal logs |
| 3.2 | Results reference real source_ids | Returned dataset IDs exist in DB |
| 3.3 | Response is relevant to the query | At least one result plausibly related to spatial navigation |

---

## Test 4 — Agent retrieves study notes

In Agent Chat, type:
```
What have I tagged about hippocampus?
```

| # | Step | Expected |
|---|------|----------|
| 4.1 | Agent calls get_study_notes tool | Study notes from DB are used in response |
| 4.2 | Response mentions the tag from Prerequisites | "hippocampus place cells" referenced |

---

## Test 5 — Agent tags a dataset via tool

In Agent Chat, type:
```
Tag DANDI dataset 000003 with the concept "grid cells entorhinal"
```

| # | Step | Expected |
|---|------|----------|
| 5.1 | Agent calls tag_dataset tool | Tool use visible |
| 5.2 | Agent confirms success | Success message in response |
| 5.3 | Tag visible in Study Log | Navigate to Study Log; new row with "grid cells entorhinal" appears |

---

## Test 6 — Agent refuses to fabricate

In Agent Chat, type:
```
Tell me about dataset ds999999
```

| # | Step | Expected |
|---|------|----------|
| 6.1 | Agent does not invent details | Responds that the dataset was not found or is not in the DB |

---

## Test 7 — Chat history persists within session

| # | Step | Expected |
|---|------|----------|
| 7.1 | Send two messages in sequence | Both appear in chat history |
| 7.2 | Navigate away and back to Agent Chat | Prior messages still visible in session |

---

## Pass Criteria

- [x] `uv run pytest tests/ -v` — all tests pass
- [x] Agent Chat tab visible as fourth nav option
- [x] Dataset count question answered with correct number from DB
- [x] Semantic search returns real dataset IDs from ChromaDB
- [x] Study notes query returns tags from DB
- [x] Agent can tag a dataset; tag appears in Study Log
- [x] Agent does not fabricate details for unknown dataset IDs
- [x] Chat history persists within the Streamlit session

**Sign-off:** Eric Herrmann   Date: 2026-04-27
