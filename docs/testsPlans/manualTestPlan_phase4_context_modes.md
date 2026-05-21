# Manual Test Plan — Phase 4 Context Modes and Evidence Boundaries

**Epoch scope:** Agent Core, Tutor, Research, API preferences.
**Phases covered:** Learning and Research Memory Refocus Phase 4, plus pending Phase 2/3 manual carry-forward checks.
**Design source:** `docs/superpowers/specs/2026-05-19-phase4-context-modes-evidence-boundaries-design.md`
**Status:** Signed off — 2026-05-21.
**Date:** 2026-05-19

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

**Automation boundary:** Automated tests own mode validation, context-bundle
construction, prompt changes, API preference plumbing, and SSE metadata shape.
This manual plan verifies that the real API/browser workflow exposes visibly
different agent behavior across General, Contextual, and Grounded modes.

---

## Prerequisites

1. Run the automated test baseline before manual testing:

```bash
uv run pytest tests/ -q
```

Expected current baseline: full suite has only the pre-existing failures tracked
in `docs/testLog.md` and `docs/projectStatus.md`. Pass: no new failures beyond
that baseline.

2. Use a disposable DB for manual verification:

```bash
export NEURODB_DB_PATH=/tmp/neurodb_phase4_context_modes.duckdb
```

Pass: the variable points to a disposable DuckDB file.

3. Prepare Phase 2 and Phase 3 schemas:

```bash
uv run scripts/migrate_phase2_papers_topics.py
uv run scripts/migrate_phase3_claims_evidence.py
```

Pass: both migrations complete without tracebacks.

4. Seed a minimal local context fixture:

```bash
uv run python -c "
from datetime import UTC, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.schema import Base, Claim, Paper, ResearchQuestion, StudyNote
from neurodb.db.topic_store import get_or_create_topic, get_or_create_concept, link_paper_topic, link_topic_concept
from neurodb.db.claim_store import create_claim, update_claim_status, add_gap

engine = create_engine('duckdb:////tmp/neurodb_phase4_context_modes.duckdb')
Base.metadata.create_all(engine)

with Session(engine) as s:
    now = datetime.now(UTC).isoformat()
    topic = get_or_create_topic(s, 'stroke recovery', 'Neural plasticity after ischemic stroke')
    concept = get_or_create_concept(s, 'cortical remapping', 'Post-injury map reorganization')
    link_topic_concept(s, topic.id, concept.id)

    paper = s.query(Paper).filter_by(doi='10.4242/phase4-stroke').one_or_none()
    if paper is None:
        paper = Paper(
            title='Motor Recovery After Stroke',
            normalized_title='motor recovery after stroke',
            doi='10.4242/phase4-stroke',
            source_type='pubmed',
            topic_context='stroke recovery',
            status='approved',
            queued_at=now,
            reviewed_at=now,
            summary='Approved local paper summary about post-stroke motor recovery.',
        )
        s.add(paper)
        s.flush()
    link_paper_topic(s, paper.id, topic.id)

    claim = s.query(Claim).filter_by(paper_id=paper.id, text='Cortical remapping supports motor recovery after stroke.').one_or_none()
    if claim is None:
        claim = create_claim(s, paper.id, 'Cortical remapping supports motor recovery after stroke.', 'finding')
        update_claim_status(s, claim.id, 'approved')

    note = StudyNote(topic_id=topic.id, concept_tag='remapping', note_text='User note: remapping may be adaptive or maladaptive depending on lesion context.', tagged_at=now)
    s.add(note)
    s.flush()

    question = s.query(ResearchQuestion).filter_by(question='Does cortical remapping improve stroke recovery?').one_or_none()
    if question is None:
        question = ResearchQuestion(
            question='Does cortical remapping improve stroke recovery?',
            topic_context='stroke recovery',
            status='open',
            created_at=now,
            updated_at=now,
            topic_id=topic.id,
        )
        s.add(question)
        s.flush()
    add_gap(s, 'No local lesion-location dataset is linked to this question.', 'missing_dataset', question_id=question.id)
    s.commit()
    print('topic_id:', topic.id, 'question_id:', question.id)
"
```

Pass: command prints a `topic_id` and `question_id`.

---

## Manual Evals

### T1 — API preference exposes context mode

```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
```

In another terminal:

```bash
curl -s http://127.0.0.1:8001/api/preferences
curl -s -X PUT http://127.0.0.1:8001/api/preferences/context-mode \
  -H 'Content-Type: application/json' \
  -d '{"mode":"grounded"}'
curl -s http://127.0.0.1:8001/api/preferences
```

Command purpose:

- First `GET /api/preferences`: reads the current saved preferences before any
  change. Expected output includes `agent_mode`, `context_mode`, and
  `relevance_threshold`; `context_mode` should default to `contextual` unless a
  previous run saved another value in the disposable DB.
- `PUT /api/preferences/context-mode`: updates the persisted context-mode
  preference to `grounded`. Expected output is a small JSON response such as
  `{"context_mode":"grounded"}`.
- Second `GET /api/preferences`: confirms the update persisted by reading the
  preferences again. Expected output includes `"context_mode":"grounded"`.

Pass: preferences include `context_mode`; update accepts `grounded` and rejects
unknown modes with HTTP 400.

### T2 — SSE emits context_summary

```bash
uv run python tests/manual/phase4_verify_context_summary.py
```

The earlier raw `curl -N` form keeps the stream open until the model finishes
its whole answer, so it can appear to run continuously while text chunks arrive.
This helper sends the same chat request, prints the first SSE event, and stops as
soon as it observes `context_summary`.

Pass: the printed event includes `"type": "context_summary"`, `context_mode`,
source counts, and active focus metadata, followed by
`PASS: context_summary was the first SSE event.`

### T3 — Tutor modes differ visibly

Open the frontend if needed:

```bash
cd frontend && npm run dev
```

Ask the Tutor the same question in all three modes:

```text
Explain cortical remapping after stroke.
```

Phase 4 does not add the polished frontend mode selector. Set each mode from a
terminal before asking the question in the Tutor chat:

```bash
curl -s -X PUT http://127.0.0.1:8001/api/preferences/context-mode \
  -H 'Content-Type: application/json' \
  -d '{"mode":"general"}'
```

Ask the question once.

```bash
curl -s -X PUT http://127.0.0.1:8001/api/preferences/context-mode \
  -H 'Content-Type: application/json' \
  -d '{"mode":"contextual"}'
```

Ask the same question again.

```bash
curl -s -X PUT http://127.0.0.1:8001/api/preferences/context-mode \
  -H 'Content-Type: application/json' \
  -d '{"mode":"grounded"}'
```

Ask the same question a third time.

Pass:

- General mode answers from model neurology knowledge and does not overstate local sources.
- Contextual mode includes NeuroDb context from the seeded topic.
- Grounded mode separates local evidence from unsupported or missing local evidence.

Fail:

- Any answer shows a provider/model error, including `Error code: 500`.
- The backend logs an uncaught ASGI exception for the chat turn.
- The answer does not visibly change when the mode changes.

Note: transient provider 5xx errors may be retried automatically by the provider
adapter, but if the final chat response is still an error, T3 is failed and
should be rerun only after the provider route is healthy.

### T4 — Research grounded mode identifies local gap

Ask Research in grounded mode:

```text
Does cortical remapping improve stroke recovery? Use my local evidence only.
```

Pass: response uses the research question/topic context, reports the approved
claim, and identifies the missing lesion-location dataset gap instead of making
an unsupported local claim.

### T5 — Regression: topic and question tools still dispatch

Ask:

```text
Get the topic bundle for stroke recovery.
Get the question bundle for question ID 1.
```

Pass: Tutor can still call `search_topics`/`get_topic_bundle`; Research can
still call `get_question_bundle`. No tool dispatch errors.

### T6 — Carry-forward from Phase 2 T7: Tutor topic tools and queue_source

Use the API server from T1, or start it if it is not running:

```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
```

In a second terminal, start the frontend dev server:

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`, navigate to Chat, and select Neuro Tutor.

| # | Step | Expected |
|---|------|----------|
| 6.1 | Send: "What topics do I have in NeuroDb about stroke?" | Tutor calls `search_topics` with query `stroke`; response references the stroke recovery topic or says no topics found; no tool dispatch error |
| 6.2 | Send: "Give me a full context bundle for the stroke recovery topic" | Tutor calls `get_topic_bundle`; response includes linked papers, concepts, or notes, or says the bundle is empty if none are linked |
| 6.3 | Send: "Add this paper to my knowledge library about stroke recovery: title 'Motor Recovery After Stroke', doi '10.9999/test', summary 'RCT of motor rehab', topics: stroke recovery" | Tutor calls `queue_source` with a topics array containing `stroke recovery`; confirms the paper was queued |

After step 6.3, verify the topic link:

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.db.topic_store import search_topics, get_topic_bundle

engine = create_engine('duckdb:////tmp/neurodb_phase4_context_modes.duckdb')
with Session(engine) as s:
    topics = search_topics(s, 'stroke recovery')
    if topics:
        bundle = get_topic_bundle(s, topics[0]['id'])
        print('papers in bundle:', [p['title'] for p in bundle['papers']])
    else:
        print('no stroke recovery topic found')
"
```

Pass: all three Tutor steps complete without errors and `Motor Recovery After Stroke`
appears in the topic bundle paper list.

### T7 — Carry-forward from Phase 2 T8: Knowledge Library PaperItem UI

With the API and frontend servers running from T6:

| # | Step | Expected |
|---|------|----------|
| 7.1 | Navigate to the Knowledge Library panel in the frontend | Panel loads without console errors |
| 7.2 | If a paper was added in T6.3, confirm it appears in the list | Paper row is displayed with title, source type, and status |
| 7.3 | Open browser devtools -> Network tab; reload the Knowledge Library panel | API response for `/api/knowledge-library` contains objects with `id`, `title`, `doi`, `status`, `source_type`, and `summary`; no frontend type errors related to KnowledgeSource/PaperItem rename |

Pass: Knowledge Library panel renders; no JS console errors related to missing
or renamed paper fields.

### T8 — Carry-forward from Phase 3 T8: Research agent tools via chat UI

With the API and frontend servers running, select Neuro Research.

| # | Step | Expected |
|---|------|----------|
| 8.1 | Send: "Record a research question: 'Does BDNF expression predict LTP magnitude?' with topic context 'neurotrophic signaling'" | Agent calls `record_research_question`; confirms question recorded |
| 8.2 | Send: "Get the full context bundle for research question ID 1" | Agent calls `get_question_bundle`; response shows question, topic if linked, hypotheses, claims, and gaps, or states bundle is empty if nothing linked |
| 8.3 | Send: "Extract candidate claims from paper ID 1" | Agent calls `extract_claims`; lists candidate claims from the paper title, abstract, or summary; no dispatch error |
| 8.4 | Send: "Approve claim ID 1" | Agent calls `update_claim_status` with `status=approved`; confirms update |
| 8.5 | Send: "Draft a hypothesis titled 'BDNF drives LTP' with mechanism 'BDNF activates TrkB signaling, potentiating synaptic strength' and no free-text evidence" | Agent calls `draft_hypothesis` with no evidence array or an empty one; confirms hypothesis saved; no missing-evidence parameter error |
| 8.6 | Send: "Link claim ID 1 to hypothesis ID 1 as supporting evidence" | Agent calls `add_evidence_link`; confirms link created |
| 8.7 | Send: "Add a gap: we lack human electrophysiology data to confirm this in vivo, gap type missing_dataset, for question ID 1" | Agent calls `add_gap`; confirms gap recorded |
| 8.8 | Send: "Resolve gap ID 1" | Agent calls `resolve_gap`; confirms gap resolved |
| 8.9 | Send: "Before answering this question about LTP, what context do you have?" | Agent calls `get_question_bundle` proactively before answering, or explicitly says it is checking context |

Pass: all Research tool dispatches complete without errors; responses reflect DB
state and do not invent local evidence.

---

## Pass Criteria

All of the following must be true before signing off:

- [x] T1: context mode preference GET/PUT works and validates modes
- [x] T2: chat SSE emits `context_summary` with mode, focus, counts, warnings
- [x] T3: Tutor behavior differs across General, Contextual, and Grounded modes
- [x] T4: Research grounded mode identifies local evidence gaps
- [x] T5: Phase 2/3 topic and question tools still dispatch
- [x] T6: Phase 2 T7 carry-forward — Tutor topic tools and queue_source link topics
- [x] T7: Phase 2 T8 carry-forward — Knowledge Library renders PaperItem-shaped rows
- [x] T8: Phase 3 T8 carry-forward — Research agent tools dispatch through real server

**Sign-off:** Eric Herrmann Date: 2026-05-21
