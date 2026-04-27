# Agent P2 Manual Test Plan — Embedding Layer (ChromaDB + SPECTER2)

**Status:** ✅ Signed off 2026-04-27
**Tester:** Eric Herrmann
**Scope:** SPECTER2 model download, dataset embedding on ingest, study note embedding on tag/delete, vector store persistence
**Date:** <!-- fill in on execution -->

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

```bash
git status        # confirm on main, clean working tree
uv sync           # install dependencies (includes chromadb, sentence-transformers)
uv run pytest tests/ -v   # all 84 automated tests must pass
```

Note: The first ingest or tag after a clean install will download the
`allenai/specter2_base` model (~440 MB). This is a one-time download cached
by HuggingFace in `~/.cache/huggingface/`.

---

## Test 1 — Ingest triggers dataset embedding

```bash
uv run scripts/ingest.py --source dandi --limit 5
```

Expected output includes:
```
Ingest complete: run_id=N, source=dandi, at=<timestamp>
Embedding datasets into vector store…
Embedded 5 dataset(s).
```

| # | Step | Expected |
|---|------|----------|
| 1.1 | Ingest exits without error | Exit code 0 |
| 1.2 | "Embedding datasets" line printed | Model loads (first run may take 30–60 s) |
| 1.3 | "Embedded N dataset(s)" printed | Count matches ingest limit |
| 1.4 | `neurodb_chroma/` directory created | ChromaDB persists alongside `neurodb.duckdb` |

```bash
ls neurodb_chroma/
```

Expected: directory exists with ChromaDB files inside.

---

## Test 2 — Re-ingest is idempotent in vector store

```bash
uv run scripts/ingest.py --source dandi --limit 5
```

| # | Step | Expected |
|---|------|----------|
| 2.1 | Re-ingest completes without error | Exit code 0 |
| 2.2 | Count still shows same number | Same 5 datasets, no duplicate embeddings |

---

## Test 3 — Study note tag embeds the note

```bash
# Get a DANDI source_id that is ingested
uv run scripts/query_cli.py --sql "SELECT source_id FROM dandi_datasets LIMIT 1"

uv run scripts/study.py tag \
  --source dandi \
  --id <source_id> \
  --concept "place cells hippocampus" \
  --section "Augustine Ch24 p.580" \
  --note "spatial navigation electrophysiology"
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | Tag command exits without error | `Tagged dandi:<id> → 'place cells hippocampus'` |
| 3.2 | No error about vector store | No exception printed |

---

## Test 4 — Delete tag removes note from vector store

```bash
# Get the tag id just created
uv run scripts/query_cli.py --sql "SELECT id FROM study_notes ORDER BY id DESC LIMIT 1"

uv run scripts/study.py delete <tag_id>
```

| # | Step | Expected |
|---|------|----------|
| 4.1 | Delete command exits without error | `Deleted tag id=N.` |
| 4.2 | Tag no longer in DB | `study_notes` count decremented |

```bash
uv run scripts/query_cli.py --sql "SELECT COUNT(*) FROM study_notes"
```

---

## Test 5 — UI: tag and delete update vector store

Start Streamlit:
```bash
uv run streamlit run src/neurodb/ui/app.py
```

Open `http://localhost:8501`.

| # | Step | Expected |
|---|------|----------|
| 5.1 | App loads without error | No ChromaDB or model exception in terminal |
| 5.2 | Navigate to Study Log, save a tag | Green success message; no error in terminal |
| 5.3 | Select the new tag row, click Delete Tag | Row removed; no error in terminal |

---

## Test 6 — Vector store persists across restarts

```bash
# Stop Streamlit (Ctrl+C), then restart
uv run streamlit run src/neurodb/ui/app.py
```

| # | Step | Expected |
|---|------|----------|
| 6.1 | App loads without error | `neurodb_chroma/` reused; no re-download |
| 6.2 | Previously embedded datasets are still in vector store | No re-embedding on startup |

---

## Pass Criteria

- [ ] `uv run pytest tests/ -v` — all 84 tests pass
- [ ] `neurodb_chroma/` directory created after first ingest
- [ ] Ingest prints "Embedded N dataset(s)." with correct count
- [ ] Re-ingest is idempotent (no duplicate embeddings, same count)
- [ ] CLI tag embeds the note without error
- [ ] CLI delete removes the note from vector store without error
- [ ] UI save and delete call embed/remove hooks without terminal errors
- [ ] Vector store persists across server restarts (no re-download)

**Sign-off:** Eric Herrmann   Date: 2026-04-27
