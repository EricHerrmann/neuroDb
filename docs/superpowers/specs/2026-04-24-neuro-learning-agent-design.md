# NeuroDb Learning Agent — Design Specification

**Date:** 2026-04-24
**Author:** Eric Herrmann
**Status:** Pending user review

---

## Purpose

Extend the neuroDb platform with an AI-assisted learning layer that reinforces neuroscience study (currently Augustine et al., *Neuroscience*, 7th ed.) through opportunistic exploration of real public datasets, personal study tagging, and a context-persistent AI agent. The system grows in capability as the database grows and as the user's neuroscience knowledge deepens.

---

## Learning Model

**Style:** Confirmation → depth-drilling. The user confirms that a concept from reading is real and represented in data, then drills deeper into what that data actually shows.

**Engagement:** Explorer → builder. Exploration surfaces gaps; building fills them. Both reinforce learning.

**Artifact goal:** Opportunistic — the user tags and explores when something sparks curiosity, not on a fixed schedule. The system accumulates a concrete record of what real data exists for each studied concept without imposing structure.

---

## Value Threshold Principle

This principle governs all component and model choices throughout all phases:

> **Local model** for retrieval and indexing — tasks where quality is good enough at current scale and the output is data, not insight.
> **Claude API** for reasoning and synthesis — tasks where nuanced understanding of context changes the quality of the answer.
> **Upgrade trigger:** revisit the embedding model when semantic search results consistently miss relevant datasets, or when the research questions outgrow the model's domain coverage. Not before.

### What the Claude API earns its keep on

| Task | Rationale |
|------|-----------|
| Agent reasoning — interpreting questions, deciding which tools to call, synthesizing answers from multiple sources | Synthesis over structured + semantic data; a local model cannot do this reliably |
| Session summary generation at conversation end | Distills what was learned; quality here compounds into P4 context persistence |
| Study tag suggestions — agent proposes a concept tag for a dataset the user is exploring | Nuanced judgment; incorrect tags pollute the neuro_research collection |

Everything else stays local until a specific quality gap justifies an upgrade.

---

## Architecture Overview

The system adds three new layers on top of the existing neuroDb platform. The existing DuckDB + Streamlit core is untouched until P2 adds the embedding hook.

```
┌─────────────────────────────────────────────────────────────┐
│  DATA SOURCES (existing)                                     │
│  OpenNeuro · Allen Brain · NeuroVault · DANDI               │
└────────────────────────┬────────────────────────────────────┘
                         │ ingest.py (existing)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  DUCKDB  neurodb.duckdb  (existing + P1 addition)           │
│                                                              │
│  Existing: datasets_index, source tables, v_all_datasets    │
│  P1 new:   study_notes  (concept tags linked to datasets)   │
└──────────┬──────────────────────────────────────────────────┘
           │ P2: auto-embed on every write (ingest + tag)
           ▼
┌─────────────────────────────────────────────────────────────┐
│  CHROMADB  neurodb.chroma/  (P2)                            │
│                                                              │
│  Collection: neuro_research                                  │
│    · dataset embeddings (title, description, paradigm,      │
│      brain_regions)                                          │
│    · study note embeddings                                   │
│                                                              │
│  Collection: agent_context  (P4)                            │
│    · session summaries (concepts covered, datasets          │
│      explored, user knowledge state)                         │
└──────────┬──────────────────────────────────────────────────┘
           │ P3: agent reads both stores at query time
           ▼
┌─────────────────────────────────────────────────────────────┐
│  CLAUDE AGENT  (P3)                                          │
│  Streamlit Agent Chat tab alongside existing UI tabs        │
│                                                              │
│  Tools:  query_db(sql)              → DuckDB               │
│          semantic_search(query)     → ChromaDB neuro_research│
│          get_study_notes(concept)   → DuckDB study_notes    │
│          tag_dataset(...)           → DuckDB + ChromaDB     │
│                                                              │
│  P4: retrieves relevant session summaries from              │
│  agent_context at session start → injects as system context │
└─────────────────────────────────────────────────────────────┘
```

### Two ChromaDB Collections — Roles and Asymmetry

| Collection | Purpose | Write pattern | Read pattern |
|------------|---------|---------------|--------------|
| `neuro_research` | Semantic index of datasets and study notes | Upsert on ingest + tag | Searched by agent at query time |
| `agent_context` | Cross-session memory of conversations | Append-only (summaries only) | Retrieved at session start |

`neuro_research` is a mirror with enrichment — it reflects DuckDB data in semantic form and must stay in sync. `agent_context` is append-only — conversation summaries only go in, never get updated.

### DuckDB vs ChromaDB — Why Both

DuckDB is the source of truth: typed schema, FK constraints, provenance tracking, ACID transactions, cross-source JOINs, reproducibility lineage. ChromaDB is a semantic index over that truth: embedding-based similarity search, document retrieval, session memory.

If ChromaDB is lost or corrupted, a re-embed script rebuilds it entirely from DuckDB. The reverse is not possible. DuckDB is always written first; ChromaDB writes are secondary and non-blocking.

---

## Embedding Model

**Default:** `allenai/specter2` — local, free, trained on scientific paper abstracts, understands neuroscience vocabulary (retinotopic, somatosensory cortex, LFP recording, ISH) from day one.

**Config-driven for upgrade path:**
```python
EMBEDDING_MODEL = config.get("embedding_model", "allenai/specter2")
```

Upgrading the embedding model requires one config change and a re-embed run. No architectural changes.

---

## Phase Map

| Phase | What's built | Stores involved | Gate |
|-------|-------------|-----------------|------|
| P1 | Study tag layer: DuckDB schema, CLI, Streamlit Study Log UI | DuckDB only | Manual test plan sign-off |
| P2 | Embedding layer: auto-embed datasets + study notes on write | DuckDB + ChromaDB neuro_research | Manual test plan sign-off |
| P3 | Claude agent: tool use, Streamlit Agent Chat tab | DuckDB + ChromaDB neuro_research (read) | Manual test plan sign-off |
| P4 | Context persistence: session summaries, cross-session memory | + ChromaDB agent_context (read/write) | Manual test plan sign-off |

Each phase gate requires: automated tests passing + user execution of the phase manual test plan + user sign-off. No phase begins until the prior phase is signed off.

---

## Component Design Per Phase

### P1 — Study Tag Layer

**New DuckDB table: `study_notes`**

| Column | Type | Purpose |
|--------|------|---------|
| `id` | int PK (sequence) | Consistent with existing schema |
| `index_id` | int FK → `datasets_index.id` | Links tag to a specific ingested dataset |
| `concept_tag` | varchar(128) | e.g. `"retinotopic mapping"`, `"auditory cortex"` |
| `section_ref` | varchar(64) | e.g. `"Augustine Ch13 p.312"` — optional |
| `note_text` | text | User's observation, question, or confirmation note |
| `tagged_at` | varchar(32) | ISO timestamp |

The tag CLI and UI resolve `(source, source_id)` → `index_id` via DuckDB lookup before writing. If the dataset is not found in `datasets_index`, the operation fails with: "Dataset not found — run ingest first."

**New script: `scripts/study.py`**

```bash
# Tag a dataset
uv run scripts/study.py tag --source dandi --id 000003 \
  --concept "primary visual cortex" --section "Augustine Ch13" \
  --note "electrode recordings in V1, matches retinotopic org discussion"

# List tags for a concept
uv run scripts/study.py list --concept "visual cortex"

# Keyword search across all tags and notes
uv run scripts/study.py search "retinotopic"
```

**UI additions**

- `src/neurodb/ui/pages/study_log.py` — new Study Log page:
  - **Browse & search** section: filterable list of all tags (by concept, source, date); shows linked dataset title alongside note
  - **Tag by ID** section: fallback form for tagging datasets found via SQL Query tab
- `src/neurodb/ui/pages/datasets.py` — inline "Tag this dataset" expander per row: opens form with concept_tag (required), section_ref (optional), note_text (optional)
- `src/neurodb/ui/app.py` — add Study Log tab

App tab layout from P1: **Dataset Explorer | SQL Query | Study Log**

**Manual test plan:** `docs/testsPlans/manualTestPlan_agent_p1.md`

---

### P2 — Embedding Layer

**New source files:**

`src/neurodb/embedder.py`
- Loads `allenai/specter2` once on import (downloaded on first run, cached by sentence-transformers)
- `embed_dataset(record: dict)` — composes text from `title + description + cognitive_paradigm + brain_regions`, generates vector, upserts to `neuro_research`
- `embed_study_note(note: dict)` — composes text from `concept_tag + note_text + section_ref`, upserts to `neuro_research`
- `rebuild_from_duckdb(session)` — re-embeds all DuckDB records; used for recovery and initial backfill
- Embedding failures: log warning, return silently — never block the calling operation

`src/neurodb/vector_store.py`
- Persistent ChromaDB client at `neurodb.chroma/` (alongside `neurodb.duckdb`)
- `NeuroResearchStore`: `upsert(doc_id, text, metadata)`, `search(query, n=5) -> list[dict]`
- `AgentContextStore`: `add_summary(text, metadata)`, `get_relevant(query, n=3) -> list[str]`
- Config-driven: `EMBEDDING_MODEL = config.get("embedding_model", "allenai/specter2")`

**Hooks into existing code (minimal surface area):**
- `ingest.py`: one call after each successful dataset write → `embedder.embed_dataset(record)`
- `study.py tag` and Study Log UI tag form: one call after study_note write → `embedder.embed_study_note(note)`

**Manual test plan:** `docs/testsPlans/manualTestPlan_agent_p2.md`

---

### P3 — AI Agent Interface

**`src/neurodb/agent.py`** — Claude API client with tool use

Four tools:

| Tool | Action | When used |
|------|--------|-----------|
| `query_db(sql: str)` | Runs SQL against DuckDB, returns rows as JSON | Structured questions: counts, filters, aggregations |
| `semantic_search(query: str, n: int = 5)` | Searches ChromaDB `neuro_research` | "Find datasets related to X" |
| `get_study_notes(concept: str)` | Queries `study_notes` by concept_tag | "What have I tagged about X?" |
| `tag_dataset(source, source_id, concept, note)` | Writes to DuckDB + ChromaDB | Agent proposes tag in chat text; user types "yes" or "confirm" to trigger write — agent never writes a tag without explicit user confirmation |

System prompt establishes: agent role, awareness of the four data sources and their fields, Value Threshold Principle constraint (always ground answers in real dataset IDs, never hallucinate data), and injected session context from P4.

`query_db` error handling: if Claude generates invalid SQL, the tool returns the error message; Claude retries with corrected query (one retry max, then reports failure to user).

**`src/neurodb/ui/pages/chat.py`** — Streamlit Agent Chat page
- `st.chat_message` for scrollable conversation history
- Conversation state in `st.session_state`
- Optional topic input at session start
- "End session" button triggers P4 summary generation; closing the browser tab without clicking this button does not generate a session summary — that session's context is not persisted
- On session start: calls `session_manager.start_session(topic)` to retrieve prior context

**`src/neurodb/ui/app.py`** — add Agent Chat tab

App tab layout from P3: **Dataset Explorer | SQL Query | Study Log | Agent Chat**

**Manual test plan:** `docs/testsPlans/manualTestPlan_agent_p3.md`

---

### P4 — Context Persistence

**`src/neurodb/session_manager.py`**

- `start_session(topic: str) -> str` — searches `agent_context` for prior summaries relevant to the topic, returns top 3 formatted as a system prompt context block; returns session_id
- `end_session(session_id: str, conversation: list[dict]) -> None` — calls Claude API to generate session summary, embeds via SPECTER2, stores in `agent_context`

**Session summary format** (Claude generates):
```
Topic: visual cortex / retinotopic mapping
Date: 2026-04-24
Concepts covered: retinotopic organization, V1 electrode recordings, cortical magnification
Datasets explored: DANDI:000003, OpenNeuro:ds003684
Knowledge state: understands retinotopic mapping conceptually; exploring electrophysiology evidence
Open questions: cortical magnification factor in V1 — to revisit
```

**Context injection at session start:**
```
[System prompt addition]
Prior sessions relevant to this topic:
- 2026-04-17: visual cortex / receptive fields — covered orientation selectivity,
  explored NeuroVault maps for primary visual cortex. User understands basic V1 organization.
- 2026-04-10: somatosensory cortex — covered S1 topographic map, tagged 3 datasets.
```

**Session summary failure:** log warning, session ends cleanly — losing one summary is acceptable. Do not block exit.

**Manual test plan:** `docs/testsPlans/manualTestPlan_agent_p4.md`

---

## Data Flow

### Path 1 — Ingest (existing + P2 hook)
```
ingest.py → fetch API → normalize → write DuckDB
                                         └── [P2] embed_dataset() → upsert neuro_research
                                               (failure: log warning, ingest continues)
```

### Path 2 — Study Tag (CLI or UI)
```
study.py tag / Study Log UI → lookup index_id → write study_notes (DuckDB)
                                                      └── [P2] embed_study_note() → upsert neuro_research
```

### Path 3 — Agent Query (P3)
```
User message → [P4] get session context from agent_context
             → Claude API (tool_use loop):
                 semantic_search() → ChromaDB neuro_research
                 query_db()        → DuckDB
                 get_study_notes() → DuckDB study_notes
                 tag_dataset()     → DuckDB + ChromaDB (if user approves)
             → Claude synthesizes → response grounded in real dataset IDs
```

### Path 4 — Session Lifecycle (P4)
```
Session start: start_session(topic) → search agent_context → inject top 3 summaries as system context

Session end:   end_session(id, conversation)
                 → Claude API: summarize conversation
                 → embed summary (SPECTER2)
                 → store in agent_context
```

---

## Error Handling

| Failure | Behavior |
|---------|----------|
| ChromaDB unavailable on ingest | Log warning, ingest completes — DuckDB is authoritative |
| SPECTER2 embedding fails | Log warning, skip embedding — re-embed script can backfill |
| Claude API fails (agent) | Show error in chat, suggest equivalent CLI query |
| Agent generates bad SQL | Tool returns error; Claude retries once with corrected query |
| study_notes FK lookup fails | Clear error: "Dataset not found — run ingest first" |
| Session summary fails | Log warning, session ends cleanly without storing summary |
| agent_context empty (first session) | Agent starts with no prior context — cold start is expected |

---

## Testing Strategy

### Guiding Rules

- **Unit tests:** mock dependencies to isolate the unit under test
- **Integration tests:** real systems throughout — real DuckDB (temp file), real ChromaDB (temp directory), real SPECTER2 model, real Claude API for P3/P4 agent tests
- **Claude API integration tests:** marked `@pytest.mark.live`; use a fixed narrow prompt designed to trigger a predictable tool call sequence; assert tool was called with correct parameters (not the exact text of Claude's response)
- **Manual test plans:** written to `docs/testsPlans/` before each phase is implementable; user execution and sign-off is the phase gate

### Per-Phase Tests

**P1**
- Unit: `study_notes` schema; FK constraint enforced on unknown (source, source_id)
- Unit: `study.py` tag, list, search subcommands with fixture data
- Integration: tag a dataset → query `study_notes` → confirm row visible with correct fields
- Manual: `docs/testsPlans/manualTestPlan_agent_p1.md`

**P2**
- Unit: `embedder.py` — compose text from dataset record, returns vector of correct dimension
- Unit: `vector_store.py` — upsert + search round-trip against real local ChromaDB temp instance
- Integration: ingest fixture dataset → confirm `neuro_research` collection count increments
- Integration: add study tag → confirm note appears in semantic search results
- Integration: drop ChromaDB → run re-embed script → confirm count matches DuckDB record count
- Manual: `docs/testsPlans/manualTestPlan_agent_p2.md`

**P3**
- Unit: each tool function tested independently with mocked DuckDB/ChromaDB
- Integration (`@pytest.mark.live`): fixed prompt → assert correct tool called with correct parameters
- Manual: `docs/testsPlans/manualTestPlan_agent_p3.md`

**P4**
- Unit: `start_session` — real ChromaDB temp instance, confirm correct summaries retrieved and formatted
- Unit: `end_session` — real ChromaDB temp instance + `@pytest.mark.live` for Claude summarization call
- Integration (`@pytest.mark.live`): full session lifecycle — start → exchange messages → end → start new session → confirm prior context appears in system prompt
- Manual: `docs/testsPlans/manualTestPlan_agent_p4.md`

---

## File Map

```
neuroDb/
├── neurodb.duckdb                          existing
├── neurodb.chroma/                         P2 new — ChromaDB persistent directory
├── scripts/
│   └── study.py                            P1 new — tag/list/search CLI
├── src/neurodb/
│   ├── schema.py                           P1 modified — add study_notes table
│   ├── embedder.py                         P2 new
│   ├── vector_store.py                     P2 new
│   ├── agent.py                            P3 new
│   ├── session_manager.py                  P4 new
│   └── ui/
│       ├── app.py                          P1 modified — add Study Log tab; P3 add Agent Chat tab
│       └── pages/
│           ├── datasets.py                 P1 modified — add inline tag expander
│           ├── study_log.py                P1 new
│           └── chat.py                     P3 new
├── tests/
│   ├── unit/
│   │   ├── test_study_notes.py             P1
│   │   ├── test_embedder.py                P2
│   │   ├── test_vector_store.py            P2
│   │   ├── test_agent_tools.py             P3
│   │   └── test_session_manager.py         P4
│   └── integration/
│       ├── test_study_tag_flow.py          P1
│       ├── test_embedding_flow.py          P2
│       ├── test_agent_query.py             P3 (@pytest.mark.live)
│       └── test_session_lifecycle.py       P4 (@pytest.mark.live)
└── docs/
    ├── superpowers/specs/
    │   └── 2026-04-24-neuro-learning-agent-design.md   this file
    └── testsPlans/
        ├── manualTestPlan_agent_p1.md        P1 gate
        ├── manualTestPlan_agent_p2.md        P2 gate
        ├── manualTestPlan_agent_p3.md        P3 gate
        └── manualTestPlan_agent_p4.md       P4 gate
```

---

*Spec authored: 2026-04-24. Review against `NeuroDbGoals.md` and `ClaudeDbEpochPlan.md` before implementation begins.*
