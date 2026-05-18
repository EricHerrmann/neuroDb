# Phase 2 — Papers, Topics, Concepts, and Study Context

**Date:** 2026-05-18
**Status:** Design approved — ready for implementation plan
**Owner:** DB epoch (schema, migration, topic_store helper); Tutor epoch (agent tools, queue_source extension)
**Parent spec:** `docs/superpowers/specs/2026-05-18-learning-research-memory-refocus-design.md` Phase 2

---

## Goal

Add first-class `papers`, `topics`, and `concepts` tables with linking tables. Extend the Knowledge Library curation workflow so papers carry structured topic and concept links. Give the Tutor agent two new retrieval tools — `search_topics` and `get_topic_bundle` — so it can retrieve a typed context bundle for a topic without raw SQL. Generalize `StudyNote` to attach to topics, concepts, and papers in addition to datasets.

Retrieval is SQL-only in this phase. Semantic search over topics and concepts is deferred to Phase 4 when context modes and retrieval are redesigned holistically.

---

## Architecture

Three layers:

1. **Schema** — rename `knowledge_sources` → `papers`, add `topics` and `concepts` tables, add five linking tables, generalize `StudyNote`.
2. **`topic_store` helper** — DB-epoch module (`src/neurodb/db/topic_store.py`) with all write and read operations. Nothing above it calls raw SQL against these tables.
3. **Tutor agent** — two new tools (`search_topics`, `get_topic_bundle`) and an extended `queue_source` that accepts an optional `topics` array.

---

## Schema Changes

### `knowledge_sources` → `papers`

The ORM class `KnowledgeSource` is renamed to `Paper`. `__tablename__` changes from `knowledge_sources` to `papers`. All existing columns are preserved. Three columns are added:

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `abstract` | Text | yes | Full abstract text |
| `authors_json` | Text | yes | JSON array of author strings |
| `year` | Integer | yes | Publication year |

`topic_context` (free-text) is kept as a fallback for records that predate structured links. `journal` is omitted — source provenance is carried by `source_type` and `url`.

### `topics` table

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer PK | sequence |
| `name` | String(256) | unique, not null, indexed |
| `description` | Text | nullable |
| `status` | String(16) | not null, default `active` |
| `created_at` | String(32) | not null |
| `updated_at` | String(32) | not null |

Valid status values: `active`, `archived`.

### `concepts` table

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer PK | sequence |
| `name` | String(256) | unique, not null, indexed |
| `description` | Text | nullable |
| `status` | String(16) | not null, default `active` |
| `created_at` | String(32) | not null |
| `updated_at` | String(32) | not null |

### Linking tables

All five tables have a composite unique constraint on the pair of FKs.

| Table | Columns |
|---|---|
| `paper_topics` | `paper_id → papers.id`, `topic_id → topics.id` |
| `paper_concepts` | `paper_id → papers.id`, `concept_id → concepts.id` |
| `topic_concepts` | `topic_id → topics.id`, `concept_id → concepts.id` |
| `dataset_packet_topics` | `packet_id → dataset_research_packets.id`, `topic_id → topics.id` |
| `dataset_packet_papers` | `packet_id → dataset_research_packets.id`, `paper_id → papers.id` |

### `StudyNote` generalization

`index_id` becomes nullable. Three columns are added:

| Column | Type | Notes |
|---|---|---|
| `topic_id` | Integer, FK → topics.id | nullable |
| `concept_id` | Integer, FK → concepts.id | nullable |
| `paper_id` | Integer, FK → papers.id | nullable |

The unique constraint `uq_study_note_index_concept` is dropped. A check constraint replaces it: at least one of `(index_id, topic_id, concept_id, paper_id)` must be non-null.

---

## Migration

Script: `scripts/migrate_phase2_papers_topics.py`

Steps run in order, idempotently (each step checks whether the change is already applied before executing):

1. `ALTER TABLE knowledge_sources RENAME TO papers` — skip if `papers` already exists.
2. Add `abstract TEXT` to `papers` — skip if column exists.
3. Add `authors_json TEXT` to `papers` — skip if column exists.
4. Add `year INTEGER` to `papers` — skip if column exists.
5. Create `topics` table if not exists.
6. Create `concepts` table if not exists.
7. `ALTER TABLE study_notes ALTER COLUMN index_id DROP NOT NULL`.
8. Add `topic_id INTEGER REFERENCES topics(id)` to `study_notes` — skip if column exists.
9. Add `concept_id INTEGER REFERENCES concepts(id)` to `study_notes` — skip if column exists.
10. Add `paper_id INTEGER REFERENCES papers(id)` to `study_notes` — skip if column exists.
11. Drop constraint `uq_study_note_index_concept` if it exists.
12. `create_all()` to create the five linking tables.

The script is safe to re-run. After sign-off, the migration is recorded in `docs/archive/completedPhases.md`.

---

## `topic_store` Helper

**File:** `src/neurodb/db/topic_store.py`

All functions take a SQLAlchemy `Session` as first argument. All link functions are idempotent (INSERT OR IGNORE / upsert).

```python
def get_or_create_topic(session, name: str, description: str | None = None) -> Topic
def get_or_create_concept(session, name: str, description: str | None = None) -> Concept

def link_paper_topic(session, paper_id: int, topic_id: int) -> None
def link_paper_concept(session, paper_id: int, concept_id: int) -> None
def link_topic_concept(session, topic_id: int, concept_id: int) -> None
def link_packet_topic(session, packet_id: int, topic_id: int) -> None
def link_packet_paper(session, packet_id: int, paper_id: int) -> None

def search_topics(session, query: str, limit: int = 10) -> list[dict]
# SQL LIKE match against name and description
# Returns: [{id, name, description, status}, ...]

def get_topic_bundle(session, topic_id: int) -> dict
# Returns:
# {
#   "topic": {id, name, description},
#   "concepts": [{id, name, description}, ...],   # directly linked via topic_concepts only
#   "papers": [{id, title, doi, status, summary}, ...],  # directly linked via paper_topics
#   "study_notes": [{id, note_text, concept_tag, tagged_at}, ...],  # anchored to this topic_id
#   "dataset_packets": [{id, source, source_id, title, usefulness_state}, ...]  # via dataset_packet_topics
# }
# Transitive concept retrieval (concepts linked through papers) is out of scope for Phase 2.
```

---

## Tutor Agent Changes

**File:** `src/neurodb/agents/tutor_agent.py`

### New tools

**`search_topics`**

```json
{
  "name": "search_topics",
  "description": "Search for topics in the NeuroDb knowledge base by name or description keyword.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Keyword to search for."},
      "limit": {"type": "integer", "description": "Maximum results to return."}
    },
    "required": ["query"]
  }
}
```

**`get_topic_bundle`**

```json
{
  "name": "get_topic_bundle",
  "description": "Retrieve all related papers, concepts, study notes, and dataset packets for a topic.",
  "input_schema": {
    "type": "object",
    "properties": {
      "topic_id": {"type": "integer", "description": "Topic ID from search_topics."}
    },
    "required": ["topic_id"]
  }
}
```

### Extended `queue_source`

Adds optional `topics` field (array of strings). When provided, each string is resolved via `get_or_create_topic()` and linked to the queued paper via `link_paper_topic()`. Existing calls without `topics` are unaffected.

```json
{
  "topics": {
    "type": "array",
    "items": {"type": "string"},
    "description": "Topic names to link to this source."
  }
}
```

### System prompt addition

One sentence added: *"To retrieve context for a topic before answering, call search_topics to find the topic ID, then get_topic_bundle to retrieve related papers, concepts, notes, and datasets."*

---

## Code Rename Impact

All references to `KnowledgeSource` are updated to `Paper`:

| File | Change |
|---|---|
| `src/neurodb/schema.py` | Class rename, `__tablename__` rename |
| `src/neurodb/knowledge_store.py` | Import update |
| `src/neurodb/agents/tutor_agent.py` | Import update |
| `src/neurodb/api/routes/knowledge_library.py` | Import update |
| `src/neurodb/api/schemas/knowledge_library.py` | `KnowledgeSourceItem` renamed to `PaperItem` |

The API response model rename (`KnowledgeSourceItem` → `PaperItem`) is a breaking change for any frontend that imports it by name. `frontend/src/api/types.ts` is updated in the same commit.

---

## Testing

### Unit tests

**`tests/unit/test_schema_papers.py`**
- `Paper` table has all expected columns including `abstract`, `authors_json`, `year`
- `knowledge_sources` name is gone from schema metadata

**`tests/unit/test_topic_store.py`**
- `get_or_create_topic` returns same row on second call (idempotency)
- `get_or_create_concept` idempotency
- All five link functions are idempotent (second call does not raise or duplicate)
- `search_topics` returns matching topics; excludes non-matching
- `get_topic_bundle` returns correct shape: topic, concepts, papers, study_notes, dataset_packets

**`tests/unit/test_study_note_anchors.py`**
- `index_id` nullable — a note with only `topic_id` set is valid
- Check constraint rejects a note with all four anchors null
- Each single-anchor combination (index_id only, topic_id only, concept_id only, paper_id only) is accepted

**`tests/unit/test_api_knowledge_library.py`**
- Existing tests updated for `Paper`/`PaperItem` rename — no behavioral changes

### Integration test

**`tests/integration/test_phase2_topic_bundle.py`**
- Create topic, create concept, approve a paper, link all three, link a dataset packet to the topic
- Call `get_topic_bundle`; assert paper, concept, and dataset packet all appear in result
- Add a study note anchored to the topic; assert it appears in `get_topic_bundle` result

### Migration test

**`tests/unit/test_migrate_phase2.py`**
- Uses DuckDB in-memory (not SQLite) — the migration script uses `ALTER COLUMN DROP NOT NULL`, which SQLite does not support
- Run migration script against a fresh DuckDB in-memory DB seeded with one `knowledge_sources` row
- Assert the row appears in `papers` with the same data
- Assert `abstract`, `authors_json`, `year` columns exist on `papers`
- Assert `study_notes.index_id` is nullable
- Assert `topic_id`, `concept_id`, `paper_id` columns exist on `study_notes`
- Assert re-running the migration does not raise

---

## Acceptance Criteria

- A topic row can return related approved papers, concepts, study notes, and dataset packets via `get_topic_bundle` — verified by integration test
- A dataset packet can be linked to papers and topics — verified by integration test
- Tutor can call `search_topics` and `get_topic_bundle` without raw SQL — verified by unit tests on the helper and agent tool dispatch
- `StudyNote` accepts topic, concept, and paper anchors without a dataset — verified by unit tests
- All existing Knowledge Library tests pass after `KnowledgeSource` → `Paper` rename

---

## Out of Scope

- Semantic (ChromaDB) search for topics or concepts — Phase 4
- UI pages for topic browsing — Phase 5
- API routes for creating or listing topics and concepts — Phase 5
- `Claim` and `EvidenceLink` tables — Phase 3
- Research agent changes — Phase 3 and Phase 4
