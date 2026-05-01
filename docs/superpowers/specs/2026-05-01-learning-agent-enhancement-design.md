# NeuroDb Learning Agent Enhancement — Design Specification

**Date:** 2026-05-01
**Author:** Eric Herrmann
**Status:** Approved

---

## Goals

### New Primary Goal

Use NeuroDb as an AI-assisted learning platform grounded in structured reading of *Neuroscience, 7th ed.* (Augustine et al.), with the agent accumulating chapter-by-chapter knowledge as the user progresses through the book. Real datasets provide evidence for textbook concepts; the agent connects reading to data.

The system is designed to grow beyond a single textbook — additional books, curated papers, and promoted DB datasets are all first-class learning sources.

### Deferred Goal

The brain plasticity / language-culture hypothesis testing work (DB Epochs 7–8) is preserved but moved to deferred status. It remains the natural long-term output of a mature learning layer: once chapter knowledge and tagged datasets accumulate, hypothesis testing is the next logical step.

---

## Architecture

### Single Agent, Mode-Aware Tool Set

The existing `NeuroAgent` becomes mode-aware. A `mode` field (`learning` | `discovery`) is stored in Streamlit session state and toggled from the UI. The agent object is unchanged — what changes is the tool list passed to Claude on each call. The agent's session memory, chapter context, and conversation history are shared across both modes.

```
┌─────────────────────────────────────────────────────────┐
│  NeuroAgent (single instance, shared context)            │
│                                                          │
│  mode = "learning"        mode = "discovery"             │
│  ─────────────────        ───────────────────            │
│  query_db                 query_db                       │
│  semantic_search          semantic_search                │
│  get_study_notes          get_study_notes                │
│  tag_dataset              tag_dataset                    │
│                           search_external(source)        │
│                           suggest_import(...)            │
│                           suggest_learning_source(...)   │
│                           suggest_new_source(...)        │
└─────────────────────────────────────────────────────────┘
```

**Mode enforcement is hard:** in learning mode, external tools are not registered in the Claude API call — the LLM cannot call them regardless of instruction. The user flips the mode explicitly; the agent never switches on its own.

### Discovery Tool Descriptions

| Tool | Behavior |
|---|---|
| `search_external(source, query)` | Dispatches to the named connector's external API. `source` accepts a specific connector name (e.g. `"openneuro"`) or `"all"` to search across every registered connector. Picks up new connectors automatically as they are added to the registry. |
| `suggest_import(source, source_id, title, reason)` | Writes a candidate to `import_queue`. Nothing is ingested until the user confirms in the Suggestions UI tab. |
| `suggest_learning_source(type, reference, display_name, reason)` | Queues a paper, study, or dataset as a candidate learning source in the Suggestions tab. |
| `suggest_new_source(reference, display_name, reason)` | Logs an entirely new database or API as a candidate connector in `source_suggestions`. Adding it to the system still requires building a connector — this is a deliberate engineering step, not an automatic one. |

### Chapter Context

Chapter context is injected as a line in the system prompt when set. The agent uses it to bias answers and discovery suggestions without restricting its tools or scope.

Example injection:
```
The user is currently reading Ch12 — Central Visual Pathways.
Topics: retinotopy, LGN, V1 laminar organization, orientation selectivity,
ocular dominance columns, dorsal/ventral streams, critical period plasticity.
```

Context is set per-session and does not persist across sessions — intentionally lightweight.

---

## Learning Source Registry

### Purpose

A unified registry of all sources the user is learning from: textbooks (structured by chapter), curated papers and studies, and DB datasets promoted to reference status. The registry is the backbone of chapter context lookup and discovery agent suggestions.

### `chapter_registry.py`

A static Python module seeded with Augustine 7th ed. chapters. Structure:

```python
REGISTRY = {
    "augustine_7e": {
        "display_name": "Neuroscience, 7th ed. — Augustine et al.",
        "chapters": {
            12: {
                "title": "Central Visual Pathways",
                "topics": [
                    "retinotopy", "LGN", "V1 laminar organization",
                    "orientation selectivity", "ocular dominance columns",
                    "dorsal/ventral streams", "critical period plasticity",
                ]
            },
            # ... all chapters
        }
    }
}
```

This module is the seed source for the `learning_sources` table. Additional books are added by inserting new top-level keys and their chapter structures.

### Chapter Input UX

The user types a short reference (e.g. `Ch12`) into the chapter annotation field in the UI sidebar. The system looks it up in the registry and displays a confirmation:

> **Ch12 — Central Visual Pathways**
> Topics: retinotopy, LGN, V1 laminar organization, orientation selectivity, ocular dominance columns, dorsal/ventral streams, critical period plasticity

The user confirms or dismisses. On confirmation, the full title and topics are injected into the agent system prompt. If the chapter is not found in the registry, input is accepted as plain text and flagged as unrecognized.

---

## Data Model

### Design Principle

Structured columns only for fields actively queried or filtered. Everything else in `metadata_json`. All type and status fields are open strings — new values never require a schema migration.

### `learning_sources`

```sql
CREATE TABLE learning_sources (
    id           INTEGER PRIMARY KEY,
    source_type  VARCHAR,    -- open: 'book', 'paper', 'dataset', ...
    source_key   VARCHAR UNIQUE, -- stable id: DOI, 'augustine_7e', dataset source_id
    display_name VARCHAR,
    content_json TEXT,       -- chapters/topics structure; varies by source_type
    metadata_json TEXT,      -- authors, publisher, year, url, anything else
    added_by     VARCHAR,    -- 'seed' | 'user' | 'agent'
    added_at     TIMESTAMP
)
```

One row per learning source. The entire Augustine 7th ed. is a single row; all chapter data lives in `content_json` keyed by chapter number. Seeded at DB init. Adding a new textbook = inserting one row with `source_type='book'` and its full chapter structure in `content_json`.

### `import_queue`

```sql
CREATE TABLE import_queue (
    id           INTEGER PRIMARY KEY,
    source       VARCHAR,    -- connector name; grows as connectors grow
    source_id    VARCHAR,
    title        VARCHAR,
    reason       TEXT,       -- agent's reasoning at suggestion time
    chapter_ref  VARCHAR,    -- chapter context active when suggested
    status       VARCHAR,    -- open: 'pending', 'imported', 'dismissed'
    metadata_json TEXT,      -- full API response snapshot
    suggested_at TIMESTAMP,
    resolved_at  TIMESTAMP
)
```

### `source_suggestions`

```sql
CREATE TABLE source_suggestions (
    id              INTEGER PRIMARY KEY,
    suggestion_type VARCHAR,  -- open: 'new_connector', 'learning_source', ...
    reference       VARCHAR,
    display_name    VARCHAR,
    reason          TEXT,
    status          VARCHAR,  -- open: 'pending', 'accepted', 'dismissed'
    metadata_json   TEXT,     -- URL, DOI, contact, notes, anything
    suggested_at    TIMESTAMP
)
```

---

## UI Changes

### Mode Toggle

A `Learning | Discovery` switch in the chat sidebar, above the message input. Flipping it updates session state; the agent picks up the new tool set on the next message. No page reload.

### Chapter Annotation

A text input in the chat sidebar below the mode toggle. Accepts a chapter reference (e.g. `Ch12`). On entry, looks up the registry and displays the confirmation block (title + topics). Confirmed context persists for the session.

### Suggestions Tab

A new **Suggestions** tab alongside Datasets, Query, and Study Log. Displays all pending rows from `import_queue` and `source_suggestions`. Each row shows:
- Source, ID, title, agent's reason, chapter context at suggestion time
- **Import** button — runs the existing ingest CLI for that source + ID
- **Promote** button (learning sources) — moves the candidate into `learning_sources`
- **Dismiss** button — soft-deletes (sets status to `dismissed`); dismissed items do not resurface

### Learning Registry Tab

A new **Learning Registry** tab alongside Suggestions. Gives the user a transparent view of everything in `learning_sources` so they can verify seeding, review promoted entries, and catch errors.

Display is organized by `source_type`:

**Books** — expandable per book. Each book shows its `display_name` and an expandable list of chapters. Each chapter row shows chapter number, title, and topic list. Chapters not yet in the registry are visually absent (no placeholder rows — the registry grows incrementally).

**Papers and Studies** — flat list showing display name, reference (DOI or source_id), and topic tags. Added by agent promotion or manual entry.

**Datasets** — flat list showing display name, source connector, source_id, and topic tags. Promoted from the DB via the Suggestions tab.

Each entry has a **Remove** button (soft-delete with confirmation prompt). A minimal **Add** form at the bottom of each section allows manual entry of any source type.

**Deferred to a later phase:** editing existing entries in place, reordering chapters, bulk import from a structured file.

---

## Testing Requirements

Following project standards:

- Unit tests for `chapter_registry` lookup (known chapter, unknown chapter, wrong book key)
- Unit tests for all three new DB table writes (import_queue insert, source_suggestions insert, learning_sources seed)
- Integration test: discovery mode agent call with mocked external tool → confirm row appears in `import_queue`
- Integration test: learning mode agent call → confirm external tools are not present in the tool list passed to Claude
- Integration test: chapter annotation lookup → confirm correct title + topics returned and injected into system prompt
- Idempotency: re-seeding `learning_sources` from `chapter_registry` does not create duplicate rows
- Unit test: registry query returns correct grouped structure (books with chapters, papers, datasets separately)
- Unit test: remove entry sets soft-delete flag and entry does not appear in subsequent registry query

---

## Out of Scope for This Phase

- Building new source connectors (that is a separate engineering decision per connector)
- Automatic import (user confirmation is always required)
- Persistent chapter context across sessions (per-session only for now)
- Full chapter registry for all 30 chapters at once — registry is built incrementally as chapters are read
