# Manual Test Plan — DB Phase 2: Papers, Topics, Concepts, and Study Context

**Epoch scope:** DB epoch (schema, migration, topic_store helper); Tutor epoch (agent tools, queue_source extension).
**Phases covered:** Learning and Research Memory Refocus Phase 2.
**Design source:** `docs/superpowers/specs/2026-05-18-phase2-papers-topics-concepts-design.md`
**Status:** Pending sign-off.
**Date:** 2026-05-19

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

**Automation boundary:** Automated tests own ORM model structure, topic_store idempotency, StudyNote anchor constraints, migration correctness, and integration round-trips. This manual plan verifies that the migration runs cleanly against a real DuckDB file, that the Tutor agent can retrieve topic bundles through its new tools, and that the queue_source extension links topics to papers correctly.

---

## Prerequisites

1. Run the automated test baseline before manual testing:

```bash
uv run pytest tests/ -q
```

Expected current baseline: `573 passed, 9 failed, 5 warnings`.

The 9 expected failures are pre-existing config-routing failures already tracked in `docs/testLog.md`. Pass: no new failures beyond those 9.

2. Set a disposable DB path for manual verification:

```bash
export NEURODB_DB_PATH=/tmp/neurodb_phase2_manual.duckdb
```

Pass: the variable points to a disposable path, not `neurodb.duckdb`.

---

## T1 — Migration script runs cleanly on a fresh DB

**Goal:** Confirm the Phase 2 migration script creates all new tables, renames knowledge_sources to papers, and adds new columns without error.

```bash
# Remove any leftover DB from a prior run
rm -f /tmp/neurodb_phase2_manual.duckdb

# Run the migration script
uv run scripts/migrate_phase2_papers_topics.py
```

Expected output: script completes with no Python tracebacks and no DuckDB errors.

Verify the tables exist:

```bash
uv run python -c "
import duckdb
conn = duckdb.connect('/tmp/neurodb_phase2_manual.duckdb')
tables = conn.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY 1\").fetchall()
print([t[0] for t in tables])
"
```

Expected: list includes `papers`, `topics`, `concepts`, `paper_topics`, `paper_concepts`, `topic_concepts`, `dataset_packet_topics`, `dataset_packet_papers`, `study_notes`. Must NOT include `knowledge_sources`.

Verify new columns on `papers`:

```bash
uv run python -c "
import duckdb
conn = duckdb.connect('/tmp/neurodb_phase2_manual.duckdb')
cols = conn.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='papers'\").fetchall()
print([c[0] for c in cols])
"
```

Expected: list includes `abstract`, `authors_json`, `year`.

Verify nullable `index_id` and new anchor columns on `study_notes`:

```bash
uv run python -c "
import duckdb
conn = duckdb.connect('/tmp/neurodb_phase2_manual.duckdb')
cols = conn.execute(\"SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name='study_notes'\").fetchall()
for c in cols: print(c)
"
```

Expected: `index_id` has `is_nullable = YES`. Columns `topic_id`, `concept_id`, `paper_id` are present.

**Pass:** Migration completes, all tables exist, knowledge_sources is gone, new columns present.

---

## T2 — Migration is idempotent

**Goal:** Running the migration script a second time against the same DB does not raise errors or duplicate any schema object.

```bash
uv run scripts/migrate_phase2_papers_topics.py
```

Expected: same clean output as T1. No "table already exists" errors, no Python tracebacks.

**Pass:** Second run completes without error.

---

## T3 — topic_store: create and link topics, concepts, papers

**Goal:** The topic_store helper creates and links objects correctly from a Python session.

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.schema import Base, Paper
from neurodb.db.topic_store import (
    get_or_create_topic, get_or_create_concept,
    link_paper_topic, link_topic_concept, search_topics, get_topic_bundle
)
import json
from datetime import datetime

engine = create_engine('duckdb:////tmp/neurodb_phase2_manual.duckdb')
Base.metadata.create_all(engine)

with Session(engine) as s:
    now = datetime.utcnow().isoformat()
    topic = get_or_create_topic(s, 'stroke recovery', 'Neural plasticity following ischemic stroke')
    concept = get_or_create_concept(s, 'cortical remapping', 'Reorganization of motor/sensory cortex maps')
    link_topic_concept(s, topic.id, concept.id)

    paper = Paper(
        title='Cortical Remapping After Stroke', doi='10.1234/test', source_type='pubmed',
        status='approved', summary='Study of remapping post-stroke.',
        added_by='user', added_at=now, updated_at=now
    )
    s.add(paper)
    s.flush()
    link_paper_topic(s, paper.id, topic.id)
    s.commit()

    results = search_topics(s, 'stroke')
    print('search_topics:', results)

    bundle = get_topic_bundle(s, topic.id)
    print('concepts:', bundle['concepts'])
    print('papers:', bundle['papers'])
"
```

Expected:
- `search_topics` returns a list with one entry: `{id, name, description, status}` for `stroke recovery`.
- `bundle['concepts']` contains `cortical remapping`.
- `bundle['papers']` contains `Cortical Remapping After Stroke`.

**Pass:** search and bundle both return the linked objects.

---

## T4 — topic_store: search_topics excludes non-matching topics

**Goal:** search_topics only returns topics matching the query.

From the same Python session (or a fresh one against the same DB):

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.db.topic_store import search_topics

engine = create_engine('duckdb:////tmp/neurodb_phase2_manual.duckdb')
with Session(engine) as s:
    results = search_topics(s, 'hippocampal plasticity')
    print('results:', results)
"
```

Expected: empty list `[]` — no topic named `hippocampal plasticity` was created.

**Pass:** search returns empty list for a term with no match.

---

## T5 — StudyNote accepts topic-only anchor (no dataset)

**Goal:** A StudyNote can be created with only a topic_id and no index_id.

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.schema import Base, StudyNote
from neurodb.db.topic_store import get_or_create_topic
from datetime import datetime

engine = create_engine('duckdb:////tmp/neurodb_phase2_manual.duckdb')
Base.metadata.create_all(engine)

with Session(engine) as s:
    topic = get_or_create_topic(s, 'stroke recovery')
    note = StudyNote(
        topic_id=topic.id,
        concept_tag='remapping overview',
        note_text='Key mechanism is activity-dependent synaptic potentiation.',
        tagged_at=datetime.utcnow().isoformat()
    )
    s.add(note)
    s.commit()
    print('Note ID:', note.id, 'topic_id:', note.topic_id, 'index_id:', note.index_id)
"
```

Expected: Note created with a valid ID, `topic_id` set, `index_id = None`.

**Pass:** Note persists without constraint violation.

---

## T6 — StudyNote appears in get_topic_bundle

**Goal:** A topic-anchored StudyNote created in T5 appears in the bundle for that topic.

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.db.topic_store import search_topics, get_topic_bundle

engine = create_engine('duckdb:////tmp/neurodb_phase2_manual.duckdb')
with Session(engine) as s:
    topics = search_topics(s, 'stroke recovery')
    bundle = get_topic_bundle(s, topics[0]['id'])
    print('study_notes:', bundle['study_notes'])
"
```

Expected: `study_notes` list contains one entry with `note_text = 'Key mechanism is activity-dependent synaptic potentiation.'`.

**Pass:** Note appears in bundle.

---

## T7 — Tutor agent: search_topics and get_topic_bundle tools reachable

**Goal:** The Tutor agent exposes search_topics and get_topic_bundle in its tool list and dispatches them without error.

Start the API server in one terminal:

```bash
uv run uvicorn neurodb.api.main:app --reload --port 8000
```

In a second terminal, start the frontend dev server:

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173` and navigate to the Chat (Tutor) panel.

| # | Step | Expected |
|---|------|----------|
| 7.1 | Send: "What topics do I have in NeuroDb about stroke?" | Agent calls search_topics tool with query "stroke"; response references stroke recovery topic or states no topics found — no tool dispatch error |
| 7.2 | Send: "Give me a full context bundle for the stroke recovery topic" | Agent calls get_topic_bundle; response includes papers, concepts, or notes attached to the topic, or states bundle is empty if none linked |
| 7.3 | Send: "Add this paper to my knowledge library about stroke recovery: title 'Motor Recovery After Stroke', doi '10.9999/test', summary 'RCT of motor rehab', topics: stroke recovery" | Agent calls queue_source with topics array containing 'stroke recovery'; confirms paper queued |

After step 7.3, verify the topic link was created:

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.db.topic_store import search_topics, get_topic_bundle

engine = create_engine('duckdb:///neurodb.duckdb')
with Session(engine) as s:
    topics = search_topics(s, 'stroke recovery')
    if topics:
        bundle = get_topic_bundle(s, topics[0]['id'])
        print('papers in bundle:', [p['title'] for p in bundle['papers']])
    else:
        print('no stroke recovery topic found')
"
```

Expected: `Motor Recovery After Stroke` appears in the papers list for the stroke recovery topic.

**Pass:** All three agent steps complete without errors; topic link verified in DB.

---

## T8 — Knowledge Library rename: PaperItem in API response

**Goal:** The Knowledge Library API returns `PaperItem`-shaped objects and the frontend Knowledge Library panel renders them correctly.

With the API server running from T7:

| # | Step | Expected |
|---|------|----------|
| 8.1 | Navigate to Knowledge Library panel in the frontend | Panel loads without console errors |
| 8.2 | If a paper was added in T7.3 (may need approval first via study.py or API): confirm it appears in the list | Paper row is displayed with title, source type, and status |
| 8.3 | Open browser devtools → Network tab; reload the Knowledge Library panel | API response for `/knowledge-library/` contains objects with `id`, `title`, `doi`, `status`, `source_type`, `summary` fields — no `KnowledgeSourceItem` type errors in console |

**Pass:** Panel renders; no JS console errors related to missing or renamed type fields.

---

## Pass Criteria

All of the following must be true before signing off:

- [ ] T1: Migration runs cleanly, all tables created, knowledge_sources gone, new columns present
- [ ] T2: Migration is idempotent (second run does not error)
- [ ] T3: topic_store creates topic, concept, paper, links them; search_topics and get_topic_bundle return correct data
- [ ] T4: search_topics returns empty for non-matching query
- [ ] T5: StudyNote with topic-only anchor persists without constraint violation
- [ ] T6: Topic-anchored StudyNote appears in get_topic_bundle result
- [ ] T7: Tutor agent dispatches search_topics and get_topic_bundle; queue_source links topics
- [ ] T8: Knowledge Library panel renders; PaperItem rename causes no frontend errors

**Sign-off:** _____________________________ Date: ___________
