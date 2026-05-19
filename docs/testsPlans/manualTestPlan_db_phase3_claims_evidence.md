# Manual Test Plan — DB Phase 3: Claims, Evidence Links, and Research Gaps

**Epoch scope:** DB epoch (schema, migration, claim_store helper); Research epoch (agent tools).
**Phases covered:** Learning and Research Memory Refocus Phase 3.
**Design source:** `docs/superpowers/specs/2026-05-19-phase3-claims-evidence-design.md`
**Status:** Pending sign-off.
**Date:** 2026-05-19

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

**Automation boundary:** Automated tests own ORM model structure, claim_store idempotency, EvidenceLink and ResearchGap CheckConstraints, migration correctness, and integration round-trips. This manual plan verifies that the migration runs cleanly against a real DuckDB file, that claim_store works from a live Python session against real data, and that the research agent dispatches the six new tools through the real server and browser.

---

## Prerequisites

1. Run the automated test baseline before manual testing:

```bash
uv run pytest tests/ -q
```

Expected: all Phase 3 automated tests pass; the 9 pre-existing config-routing failures tracked in `docs/testLog.md` remain; no new failures.

2. Set a disposable DB path for manual verification:

```bash
export NEURODB_DB_PATH=/tmp/neurodb_phase3_manual.duckdb
```

Pass: the variable points to a disposable path, not `neurodb.duckdb`.

---

## T1 — Migration script runs cleanly on a fresh DB

**Goal:** Confirm the Phase 3 migration script creates the three new tables, adds topic_id to research_questions, and makes evidence fields nullable without error.

```bash
rm -f /tmp/neurodb_phase3_manual.duckdb
uv run scripts/migrate_phase3_claims_evidence.py
```

Expected output: script completes with no Python tracebacks and no DuckDB errors.

Verify the new tables exist:

```bash
uv run python -c "
import duckdb
conn = duckdb.connect('/tmp/neurodb_phase3_manual.duckdb')
tables = conn.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY 1\").fetchall()
print([t[0] for t in tables])
"
```

Expected: list includes `claims`, `evidence_links`, `research_gaps`.

Verify `topic_id` on research_questions:

```bash
uv run python -c "
import duckdb
conn = duckdb.connect('/tmp/neurodb_phase3_manual.duckdb')
cols = conn.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='research_questions'\").fetchall()
print([c[0] for c in cols])
"
```

Expected: list includes `topic_id`.

Verify nullable evidence fields on research_hypotheses:

```bash
uv run python -c "
import duckdb
conn = duckdb.connect('/tmp/neurodb_phase3_manual.duckdb')
cols = conn.execute(\"SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name='research_hypotheses' AND column_name IN ('evidence_json','datasets_json','confounds_json')\").fetchall()
for c in cols: print(c)
"
```

Expected: all three columns show `is_nullable = YES`.

**Pass:** Migration completes, all three new tables exist, topic_id present, evidence fields nullable.

---

## T2 — Migration is idempotent

**Goal:** Running the migration script a second time does not raise errors or duplicate schema objects.

```bash
uv run scripts/migrate_phase3_claims_evidence.py
```

Expected: same clean output as T1. No errors.

**Pass:** Second run completes without error.

---

## T3 — claim_store: create claims, update status, filter by paper

**Goal:** The claim_store helper creates claims and filters them correctly.

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.schema import Base, Paper
from neurodb.db.claim_store import create_claim, update_claim_status, get_claims_for_paper
from datetime import UTC, datetime

engine = create_engine('duckdb:////tmp/neurodb_phase3_manual.duckdb')
Base.metadata.create_all(engine)

with Session(engine) as s:
    now = datetime.now(UTC).isoformat()
    paper = s.query(Paper).filter_by(doi='10.1234/claim-test').one_or_none()
    if paper is None:
        paper = Paper(
            title='Claim Test Paper', normalized_title='claim test paper',
            doi='10.1234/claim-test', source_type='pubmed', topic_context='plasticity',
            status='approved', queued_at=now,
        )
        s.add(paper)
        s.flush()

    c1 = create_claim(s, paper.id, 'LTP induces synaptic strengthening.', 'finding')
    c2 = create_claim(s, paper.id, 'Study used only male rats.', 'limitation')
    s.commit()

    print('c1 status:', c1.status)
    print('c2 status:', c2.status)

    upd = update_claim_status(s, c1.id, 'approved')
    s.commit()
    print('c1 after approve:', upd)

    claims = get_claims_for_paper(s, paper.id)
    print('claims for paper:', [(c['claim_type'], c['status']) for c in claims])
"
```

Expected:
- Both claims created with `status=candidate`.
- `update_claim_status` returns `{id: ..., status: 'approved'}`.
- `get_claims_for_paper` returns two claims, one with `status=approved` and one with `status=candidate`.

**Pass:** All three operations complete correctly.

---

## T4 — claim_store: get_approved_claims_for_topic

**Goal:** Only approved claims from papers linked to the topic are returned.

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.schema import Base
from neurodb.db.topic_store import get_or_create_topic, link_paper_topic
from neurodb.db.claim_store import get_approved_claims_for_topic

engine = create_engine('duckdb:////tmp/neurodb_phase3_manual.duckdb')

with Session(engine) as s:
    topic = get_or_create_topic(s, 'synaptic plasticity')
    s.flush()

    from neurodb.schema import Paper
    paper = s.query(Paper).filter_by(doi='10.1234/claim-test').one_or_none()
    if paper:
        link_paper_topic(s, paper.id, topic.id)
    s.commit()

    approved = get_approved_claims_for_topic(s, topic.id)
    print('approved claims:', [(c['text'][:40], c['paper_title']) for c in approved])
"
```

Expected: list contains the `finding` claim approved in T3 (`LTP induces synaptic strengthening.`); the `limitation` claim with `status=candidate` does not appear.

**Pass:** Only approved claims returned; candidate claims excluded.

---

## T5 — Evidence links: all four source types

**Goal:** Evidence links can be attached to a hypothesis from each of the four source types.

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.schema import Base, ResearchHypothesis, ResearchQuestion, StudyNote
from neurodb.db.claim_store import add_evidence_link, get_evidence_links
from datetime import UTC, datetime

engine = create_engine('duckdb:////tmp/neurodb_phase3_manual.duckdb')

with Session(engine) as s:
    now = datetime.now(UTC).isoformat()
    q = ResearchQuestion(question='Does LTP drive learning?', topic_context='plasticity',
                         status='open', created_at=now, updated_at=now)
    s.add(q)
    s.flush()

    h = ResearchHypothesis(
        question_id=q.id, title='LTP learning link', mechanism='LTP strengthens synapses.',
        predictions_json='[]', limitations='draft',
        status='draft', created_at=now, updated_at=now,
    )
    s.add(h)
    s.flush()

    from neurodb.schema import Paper
    paper = s.query(Paper).filter_by(doi='10.1234/claim-test').one_or_none()

    from neurodb.schema import Claim
    claim = s.query(Claim).filter_by(status='approved').first()

    # Link from claim
    if claim:
        add_evidence_link(s, h.id, 'supports', claim_id=claim.id)

    # Link from paper
    if paper:
        add_evidence_link(s, h.id, 'contextualizes', paper_id=paper.id)

    # Link from study note
    note = StudyNote(topic_id=1, concept_tag='LTP', note_text='LTP related note', tagged_at=now)
    s.add(note)
    s.flush()
    add_evidence_link(s, h.id, 'supports', note_id=note.id)

    s.commit()

    links = get_evidence_links(s, h.id)
    print('evidence links:')
    for lk in links:
        print(' ', lk['source_type'], lk['link_type'], lk['summary'][:40])
"
```

Expected: at least claim, paper, and note source_types appear in the links list with correct `link_type` values.

**Pass:** Each source type produces a link with correct shape; `get_evidence_links` returns all links.

---

## T6 — Research gaps: add, resolve, get_gaps

**Goal:** Gaps can be added to a question, resolved, and filtered correctly.

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.db.claim_store import add_gap, resolve_gap, get_gaps

engine = create_engine('duckdb:////tmp/neurodb_phase3_manual.duckdb')

with Session(engine) as s:
    from neurodb.schema import ResearchQuestion
    q = s.query(ResearchQuestion).first()

    g1 = add_gap(s, 'No fMRI datasets available for this topic.', 'missing_dataset', question_id=q.id)
    g2 = add_gap(s, 'No clinical trial data found.', 'missing_paper', question_id=q.id)
    s.commit()

    print('g1 status:', g1.status)
    print('g2 status:', g2.status)

    resolved = resolve_gap(s, g1.id)
    s.commit()
    print('g1 after resolve:', resolved)

    gaps = get_gaps(s, question_id=q.id)
    print('gaps for question:', [(g['gap_type'], g['status']) for g in gaps])
"
```

Expected:
- Both gaps created with `status=open`.
- `resolve_gap` returns `{id: ..., status: 'resolved'}`.
- `get_gaps` returns both gaps (open and resolved).

**Pass:** All gap operations complete correctly.

---

## T7 — get_question_bundle returns correct shape

**Goal:** A question linked to a topic returns hypotheses, approved claims, and gaps in one call.

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.db.claim_store import get_question_bundle
from neurodb.db.topic_store import get_or_create_topic

engine = create_engine('duckdb:////tmp/neurodb_phase3_manual.duckdb')

with Session(engine) as s:
    # Link the question to its topic
    topic = get_or_create_topic(s, 'synaptic plasticity')
    s.flush()

    from neurodb.schema import ResearchQuestion
    q = s.query(ResearchQuestion).first()
    q.topic_id = topic.id
    s.commit()

    bundle = get_question_bundle(s, q.id)
    print('keys:', set(bundle.keys()))
    print('question:', bundle['question'])
    print('topic:', bundle['topic'])
    print('hypotheses count:', len(bundle['hypotheses']))
    print('claims count:', len(bundle['claims']))
    print('gaps count:', len(bundle['gaps']))
"
```

Expected:
- `bundle` has keys: `question`, `topic`, `hypotheses`, `claims`, `gaps`.
- `topic` is not None and shows `name = 'synaptic plasticity'`.
- `hypotheses` contains at least one entry from T5.
- `claims` contains the approved claim from T3.
- `gaps` contains the gaps from T6.

**Pass:** Bundle returns correct shape with all linked content.

---

## T8 — Research agent tools via chat UI

**Goal:** The research agent dispatches the six new tools through the real server and browser.

Start the API server in one terminal:

```bash
uv run uvicorn neurodb.api.main:app --reload --port 8000
```

In a second terminal, start the frontend dev server:

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`, navigate to the Chat (Research) panel.

| # | Step | Expected |
|---|------|----------|
| 8.1 | Send: "Record a research question: 'Does BDNF expression predict LTP magnitude?' with topic context 'neurotrophic signaling'" | Agent calls `record_research_question`; confirms question recorded |
| 8.2 | Send: "Get the full context bundle for research question ID 1" | Agent calls `get_question_bundle`; response shows question, topic (if linked), hypotheses, claims, gaps — or states bundle is empty if nothing linked |
| 8.3 | Send: "Extract candidate claims from paper ID 1" | Agent calls `extract_claims`; lists candidate claims extracted from the paper's title/abstract/summary; no dispatch error |
| 8.4 | Send: "Approve claim ID 1" | Agent calls `update_claim_status` with status=approved; confirms updated |
| 8.5 | Send: "Draft a hypothesis titled 'BDNF drives LTP' with mechanism 'BDNF activates TrkB signaling, potentiating synaptic strength' and no free-text evidence" | Agent calls `draft_hypothesis` with no evidence array (or empty); confirms hypothesis saved; no error about missing evidence parameter |
| 8.6 | Send: "Link claim ID 1 to hypothesis ID 1 as supporting evidence" | Agent calls `add_evidence_link`; confirms link created |
| 8.7 | Send: "Add a gap: we lack human electrophysiology data to confirm this in vivo, gap type missing_dataset, for question ID 1" | Agent calls `add_gap`; confirms gap recorded |
| 8.8 | Send: "Resolve gap ID 1" | Agent calls `resolve_gap`; confirms gap resolved |

Verify the system prompt addition is present by sending:

| # | Step | Expected |
|---|------|----------|
| 8.9 | Send: "Before answering this question about LTP, what context do you have?" | Agent calls `get_question_bundle` proactively before answering, or explicitly states it's checking context — confirming the system prompt addition drives bundle-first behavior |

**Pass:** All eight tool dispatches complete without errors; agent response reflects the correct data from the DB.

---

## Pass Criteria

All of the following must be true before signing off:

- [ ] T1: Migration runs cleanly, all three new tables exist, topic_id added, evidence fields nullable
- [ ] T2: Migration is idempotent (second run does not error)
- [ ] T3: create_claim, update_claim_status, get_claims_for_paper work correctly
- [ ] T4: get_approved_claims_for_topic returns only approved claims from linked papers
- [ ] T5: add_evidence_link and get_evidence_links work for all source types
- [ ] T6: add_gap, resolve_gap, get_gaps work correctly
- [ ] T7: get_question_bundle returns correct shape with all linked content
- [ ] T8: All six research agent tools dispatch through real server without errors

**Sign-off:** _____________________________ Date: ___________
