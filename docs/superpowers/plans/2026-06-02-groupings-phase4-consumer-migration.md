# Groupings Phase 4 — Consumer Migration (read + write cutover) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every remaining consumer off the legacy `topics`/`concepts` tables and their join tables onto the unified grouping engine — both reads (bundles, claims, study-note resolution, focus resolution, paper detail) and the one live write path (paper tagging) — plus fix the question-delete cleanup gap (LOG-064) and the two UI polish items (LOG-065 hierarchy collapse, LOG-066 suggestion auto-refresh). After this phase nothing but the Phase 5 drop references the legacy tables.

**Architecture & decisions (read before starting):**
- **Source of truth is `grouping_links`.** Phase 1 backfilled links for every legacy relationship; 3a cut the question flow over. Phase 4 repoints the rest. "Papers for a topic", "concepts of a topic", "notes for a topic", "datasets for a topic" all become `grouping_links` queries keyed by `anchor_type`.
- **Two new engine read helpers** (Task 1–2): `get_anchor_ids_for_grouping(...)` and `get_grouping_bundle(...)` (the engine replacement for `topic_store.get_topic_bundle`).
- **Claims attach to topics via papers.** `get_approved_claims_for_topic(topic_id)` joins `Claim→Paper→PaperTopic`; the engine version joins `Claim→Paper→grouping_links(anchor_type='paper')` (Task 3).
- **Question→topic for bundles** is derived from the question's **confirmed** `grouping_links` (`anchor_type='question'`, grouping `type='topic'`), not the legacy `ResearchQuestion.topic_id` column. A question may now have several confirmed topic groupings, so `get_question_bundle` returns `topics: [...]` (list) and aggregates claims across them, deduped (Task 4).
- **Legacy columns stay, unused.** `ResearchQuestion.topic_id` and `StudyNote.topic_id`/`concept_id` are plain int columns (no FK since migration 012). Phase 4 stops reading/writing them; dropping the columns is deferred (DuckDB column drops are risky and out of scope). New writes go to `grouping_links`.
- **Streamlit `ui/pages/*` is out of scope** (React is primary; per scoping decision). It will read stale/empty topic data after Phase 5 — acceptable; it's slated for retirement.
- **Write paths:** only `tutor_agent` (paper tagging), `knowledge_library` (paper link add + capture/restore), and study-note topic/concept anchoring are live writers. All move to `get_or_create_grouping` + `link_grouping`.
- **One consumer per task, each with tests.** Legacy tables remain intact (dormant) until Phase 5.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, FastAPI, DuckDB (runtime) / SQLite in-memory (tests), pytest; React + TS + Vitest for Tasks 10–11.

**Spec:** `docs/superpowers/specs/2026-06-01-unified-groupings-taxonomy-design.md` (Phase 4).

**Prerequisites:** Phases 1–3 implemented. Engine lives in `src/neurodb/db/grouping_store.py`; matcher in `src/neurodb/research/grouping_matcher.py`.

**Conventions (follow exactly):**
- Store functions: `session: Session` first, `select(...)`, module-local `_now()`. Tests: in-memory SQLite, `Base.metadata.create_all`, `Session(engine)` fixture (see `tests/unit/test_grouping_store.py`).
- API tests: bare `FastAPI()`, `app.state.engine`, null stores, `include_router(prefix="/api/research"|"/api/knowledge")`, `TestClient`, `patch("threading.Thread")` to suppress the matcher (see `tests/integration/test_question_phase1.py`).
- Frontend tests: seed `QueryClient` caches with `setQueryData`; `vi.spyOn(api, …)` for mutations (see `frontend/src/pages/ResearchPanel.test.tsx`).
- Run: `uv run pytest tests/ -q`; `cd frontend && npm test`; `cd frontend && npm run build`.

---

### Task 1: Engine helper — `get_anchor_ids_for_grouping`

**Files:** Modify `src/neurodb/db/grouping_store.py`; Test `tests/unit/test_grouping_store.py` (append).

- [ ] **Step 1: Failing test** — append to `tests/unit/test_grouping_store.py`:

```python
def test_get_anchor_ids_for_grouping(session):
    from neurodb.db.grouping_store import link_grouping, get_anchor_ids_for_grouping
    g = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, g.id, "paper", 11, status="confirmed")
    link_grouping(session, g.id, "paper", 12, status="confirmed")
    link_grouping(session, g.id, "study_note", 5, status="confirmed")
    papers = get_anchor_ids_for_grouping(session, g.id, "paper")
    assert sorted(papers) == [11, 12]
    assert get_anchor_ids_for_grouping(session, g.id, "study_note") == [5]
    assert get_anchor_ids_for_grouping(session, g.id, "dataset_packet") == []
```

- [ ] **Step 2: Run** `uv run pytest tests/unit/test_grouping_store.py::test_get_anchor_ids_for_grouping -v` → FAIL (ImportError).

- [ ] **Step 3: Implement** — append to `src/neurodb/db/grouping_store.py`:

```python
def get_anchor_ids_for_grouping(
    session: Session, grouping_id: int, anchor_type: str, *, status: str | None = None
) -> list[int]:
    """Anchor ids of one type linked to a grouping (reverse of get_groupings_for_anchor)."""
    stmt = select(GroupingLink.anchor_id).where(
        GroupingLink.grouping_id == grouping_id,
        GroupingLink.anchor_type == anchor_type,
    )
    if status is not None:
        stmt = stmt.where(GroupingLink.status == status)
    return [row[0] for row in session.execute(stmt).all()]
```

- [ ] **Step 4: Run** the test → PASS.
- [ ] **Step 5: Commit** `feat(groupings): get_anchor_ids_for_grouping engine helper`.

---

### Task 2: Engine bundle — `get_grouping_bundle` (replaces `get_topic_bundle`)

Mirrors `topic_store.get_topic_bundle`'s output shape, sourced from `grouping_links`. Child concepts come from `anchor_type='grouping'` links (the backfilled `topic_concepts`); papers/notes/datasets from their anchor types.

**Files:** Modify `src/neurodb/db/grouping_store.py`; Test `tests/unit/test_grouping_store.py` (append).

- [ ] **Step 1: Failing test**:

```python
def test_get_grouping_bundle(session):
    from neurodb.db.grouping_store import link_grouping, get_grouping_bundle
    from neurodb.schema import Paper
    topic = get_or_create_grouping(session, "topic", "plasticity", description="d")
    concept = get_or_create_grouping(session, "concept", "LTP")
    p = Paper(title="P1", normalized_title="p1", source_type="paper",
              topic_context="", status="approved", queued_at=_now())
    session.add(p); session.flush()
    link_grouping(session, topic.id, "grouping", concept.id, status="confirmed")  # topic→concept
    link_grouping(session, topic.id, "paper", p.id, status="confirmed")
    bundle = get_grouping_bundle(session, topic.id)
    assert bundle["grouping"]["name"] == "plasticity"
    assert [c["name"] for c in bundle["concepts"]] == ["LTP"]
    assert [pp["id"] for pp in bundle["papers"]] == [p.id]
    assert bundle["study_notes"] == []
    assert bundle["dataset_packets"] == []


def test_get_grouping_bundle_missing(session):
    from neurodb.db.grouping_store import get_grouping_bundle
    assert get_grouping_bundle(session, 999999) == {}
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement** — append to `src/neurodb/db/grouping_store.py` (note the imports inside the function to avoid widening the module header):

```python
def get_grouping_bundle(session: Session, grouping_id: int) -> dict:
    """Engine replacement for topic_store.get_topic_bundle: related concepts,
    papers, study notes, and dataset packets for a grouping, via grouping_links."""
    from neurodb.schema import DatasetResearchPacket, Paper, StudyNote

    grouping = session.get(Grouping, grouping_id)
    if grouping is None:
        return {}

    concept_ids = get_anchor_ids_for_grouping(session, grouping_id, "grouping")
    concepts = [
        session.get(Grouping, cid) for cid in concept_ids
    ]
    paper_ids = get_anchor_ids_for_grouping(session, grouping_id, "paper")
    papers = [session.get(Paper, pid) for pid in paper_ids]
    note_ids = get_anchor_ids_for_grouping(session, grouping_id, "study_note")
    notes = [session.get(StudyNote, nid) for nid in note_ids]
    packet_ids = get_anchor_ids_for_grouping(session, grouping_id, "dataset_packet")
    packets = [session.get(DatasetResearchPacket, pid) for pid in packet_ids]

    return {
        "grouping": {"id": grouping.id, "name": grouping.name,
                     "type": grouping.type, "description": grouping.description},
        "concepts": [
            {"id": c.id, "name": c.name, "description": c.description}
            for c in concepts if c is not None
        ],
        "papers": [
            {"id": p.id, "title": p.title, "doi": p.doi, "status": p.status, "summary": p.summary}
            for p in papers if p is not None
        ],
        "study_notes": [
            {"id": n.id, "note_text": n.note_text, "concept_tag": n.concept_tag, "tagged_at": n.tagged_at}
            for n in notes if n is not None
        ],
        "dataset_packets": [
            {"id": pkt.id, "source": pkt.source, "source_id": pkt.source_id,
             "title": pkt.title, "usefulness_state": pkt.usefulness_state}
            for pkt in packets if pkt is not None
        ],
    }
```

- [ ] **Step 4: Run** both tests → PASS.
- [ ] **Step 5: Commit** `feat(groupings): get_grouping_bundle engine bundle`.

---

### Task 3: Claims for a grouping — `get_approved_claims_for_grouping`

**Files:** Modify `src/neurodb/db/claim_store.py`; Test `tests/unit/test_claim_store.py` (append).

- [ ] **Step 1: Failing test** — append to `tests/unit/test_claim_store.py` (mirror the file's existing fixture/imports; it already builds papers and claims):

```python
def test_get_approved_claims_for_grouping(session):
    from datetime import datetime, timezone
    from neurodb.schema import Claim, Paper
    from neurodb.db.grouping_store import get_or_create_grouping, link_grouping
    from neurodb.db.claim_store import get_approved_claims_for_grouping

    now = datetime.now(timezone.utc).isoformat()
    p = Paper(title="P", normalized_title="p", source_type="paper",
              topic_context="", status="approved", queued_at=now)
    session.add(p); session.flush()
    session.add(Claim(paper_id=p.id, text="claim A", claim_type="finding",
                      status="approved", created_at=now, updated_at=now))
    session.flush()
    g = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, g.id, "paper", p.id, status="confirmed")

    out = get_approved_claims_for_grouping(session, g.id)
    assert [c["text"] for c in out] == ["claim A"]
```

(If `tests/unit/test_claim_store.py` lacks a `session` fixture, copy the in-memory SQLite fixture from `tests/unit/test_grouping_store.py`.)

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement** — in `src/neurodb/db/claim_store.py`, add next to `get_approved_claims_for_topic`:

```python
def get_approved_claims_for_grouping(session: Session, grouping_id: int) -> list[dict]:
    """Approved claims of papers linked to a grouping (engine version of
    get_approved_claims_for_topic, via grouping_links instead of PaperTopic)."""
    from neurodb.schema import GroupingLink
    rows = session.execute(
        select(Claim, Paper)
        .join(Paper, Paper.id == Claim.paper_id)
        .join(GroupingLink, GroupingLink.anchor_id == Paper.id)
        .where(GroupingLink.anchor_type == "paper")
        .where(GroupingLink.grouping_id == grouping_id)
        .where(Claim.status == "approved")
    ).all()
    return [
        {"id": c.id, "text": c.text, "claim_type": c.claim_type,
         "paper_id": c.paper_id, "paper_title": p.title}
        for c, p in rows
    ]
```

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(groupings): get_approved_claims_for_grouping`.

---

### Task 4: `get_question_bundle` → engine

Derive the question's topic groupings from confirmed `grouping_links`; aggregate claims across them.

**Files:** Modify `src/neurodb/db/claim_store.py` (`get_question_bundle`); Test `tests/unit/test_claim_store.py` (append).

- [ ] **Step 1: Failing test**:

```python
def test_get_question_bundle_uses_engine_topics(session):
    from datetime import datetime, timezone
    from neurodb.schema import Claim, Paper, ResearchQuestion
    from neurodb.db.grouping_store import get_or_create_grouping, link_grouping
    from neurodb.db.claim_store import get_question_bundle

    now = datetime.now(timezone.utc).isoformat()
    q = ResearchQuestion(question="Q?", topic_context="", status="open",
                         created_at=now, updated_at=now)
    session.add(q); session.flush()
    topic = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, topic.id, "question", q.id, status="confirmed")
    p = Paper(title="P", normalized_title="p", source_type="paper",
              topic_context="", status="approved", queued_at=now)
    session.add(p); session.flush()
    link_grouping(session, topic.id, "paper", p.id, status="confirmed")
    session.add(Claim(paper_id=p.id, text="claim A", claim_type="finding",
                      status="approved", created_at=now, updated_at=now))
    session.flush()

    bundle = get_question_bundle(session, q.id)
    assert [t["name"] for t in bundle["topics"]] == ["stroke"]
    assert [c["text"] for c in bundle["claims"]] == ["claim A"]
```

- [ ] **Step 2: Run** → FAIL (current bundle returns `topic`, not `topics`, and reads `question.topic_id`).

- [ ] **Step 3: Implement** — replace the body of `get_question_bundle` in `src/neurodb/db/claim_store.py`:

```python
def get_question_bundle(session: Session, question_id: int) -> dict:
    from neurodb.db.grouping_store import get_groupings_for_anchor

    question = session.get(ResearchQuestion, question_id)
    if question is None:
        return {}

    # Topic groupings confirmed for this question (engine source of truth).
    linked = get_groupings_for_anchor(session, "question", question_id, status="confirmed")
    topics = [g for g in linked if g["type"] == "topic"]

    hypotheses = session.execute(
        select(ResearchHypothesis).where(ResearchHypothesis.question_id == question_id)
    ).scalars().all()

    seen: set[int] = set()
    claims: list[dict] = []
    for t in topics:
        for c in get_approved_claims_for_grouping(session, t["id"]):
            if c["id"] not in seen:
                seen.add(c["id"])
                claims.append(c)
    gaps = get_gaps(session, question_id=question_id)

    return {
        "question": {
            "id": question.id, "question": question.question, "status": question.status,
        },
        "topics": [
            {"id": t["id"], "name": t["name"]} for t in topics
        ],
        "hypotheses": [
            {"id": h.id, "title": h.title, "status": h.status} for h in hypotheses
        ],
        "claims": claims,
        "gaps": [
            {"id": g["id"], "description": g["description"],
             "gap_type": g["gap_type"], "status": g["status"]}
            for g in gaps
        ],
    }
```

- [ ] **Step 4: Run** → PASS. Also run `uv run pytest tests/unit/test_claim_store.py -q` to catch any test asserting the old `topic` key; update those assertions to the `topics` list (the data is engine-sourced now; do not re-add the legacy `topic_id` read).
- [ ] **Step 5: Commit** `feat(groupings): get_question_bundle derives topics from grouping_links`.

---

### Task 5: Tutor agent — bundle read + paper-tag write

**Files:** Modify `src/neurodb/agents/tutor_agent.py`; Test `tests/unit/test_tutor_agent.py` (append or adjust).

- [ ] **Step 1: Failing test** — add a focused test that the tag-paper tool writes engine links and the bundle tool reads them. Mirror the existing tutor-agent test setup; assert via `grouping_links`:

```python
def test_tutor_tag_paper_writes_grouping_link(tmp_engine):  # use the file's engine fixture
    from sqlalchemy import text
    from neurodb.agents.tutor_agent import NeuroTutorAgent  # adjust to actual class/entry
    # ... arrange a paper id `pid` in tmp_engine ...
    agent = NeuroTutorAgent(engine=tmp_engine, model_client=FakeClient(...))
    agent._execute_tag_paper_topic({"paper_id": pid, "topic_name": "plasticity"})  # adjust to real method
    with tmp_engine.connect() as conn:
        n = conn.execute(text(
            "SELECT COUNT(*) FROM grouping_links gl JOIN groupings g ON g.id=gl.grouping_id "
            "WHERE g.type='topic' AND g.name='plasticity' AND gl.anchor_type='paper' AND gl.anchor_id=:p"
        ), {"p": pid}).scalar()
    assert n == 1
```

> If the existing tutor test file has no convenient hook for the tag path, assert at minimum that `_execute_get_topic_bundle` returns engine-sourced data after seeding a grouping + link. The key requirement is: **no call to `topic_store.get_or_create_topic` / `link_paper_topic` / `get_topic_bundle` remains in `tutor_agent.py`.**

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement** — in `src/neurodb/agents/tutor_agent.py`:
  - Replace the write block (currently lines ~233-236):
    ```python
    from neurodb.db.grouping_store import get_or_create_grouping, link_grouping
    g = get_or_create_grouping(session, "topic", topic_name)
    link_grouping(session, g.id, "paper", paper_id, status="confirmed")
    ```
  - Replace `_execute_get_topic_bundle` (lines ~266-273): import and call `get_grouping_bundle` instead of `topic_store.get_topic_bundle`. The tool input is a `topic_id` that is now a **grouping id**:
    ```python
    from neurodb.db.grouping_store import get_grouping_bundle
    bundle = get_grouping_bundle(session, inputs["topic_id"])
    ```
  - Update the tool description (line ~121 / ~31) to say "grouping id" where it said "topic_id" if helpful; not required for behavior.

- [ ] **Step 4: Run** the tutor tests → PASS.
- [ ] **Step 5: Commit** `feat(groupings): tutor agent reads/writes via the grouping engine`.

---

### Task 6: Context orchestrator — focus resolution + bundle

**Files:** Modify `src/neurodb/agents/context_orchestrator.py`; Test `tests/unit/test_context_orchestrator.py` (adjust).

- [ ] **Step 1: Failing test** — assert that a topic focus resolves against `groupings` and the topic bundle comes from the engine. Seed a `topic` grouping named e.g. "plasticity" + a paper link, set active focus to that grouping id / a token matching its name, and assert the assembled context includes the paper. Mirror the file's existing orchestrator test harness.

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement** — in `src/neurodb/agents/context_orchestrator.py`:
  - `get_topic_bundle` call (line ~131-134) → `get_grouping_bundle`:
    ```python
    from neurodb.db.grouping_store import get_grouping_bundle
    topic_bundle = get_grouping_bundle(session, int(active_focus["focus_id"]))
    ```
    Adjust downstream keys: the bundle now nests under `"grouping"` rather than `"topic"`. Update the renderer (line ~441 `f"- Topic: {topic.get('name')}"`) to read `topic_bundle["grouping"]["name"]`.
  - `_resolve_focus` (lines ~286, ~299): replace `select(Topic).where(Topic.name.ilike(...))` and `session.get(Topic, focus_id)` with grouping equivalents:
    ```python
    from neurodb.schema import Grouping
    # token match:
    select(Grouping).where(Grouping.type == "topic", Grouping.name.ilike(f"%{token}%")).limit(1)
    # by id:
    g = session.get(Grouping, focus_id)
    if g is not None and g.type != "topic": g = None
    ```
  - Remove the now-unused `Topic` import (line 11) if nothing else uses it.

- [ ] **Step 4: Run** orchestrator tests → PASS.
- [ ] **Step 5: Commit** `feat(groupings): context orchestrator focus + bundle via engine`.

---

### Task 7: Knowledge library route — paper links read + capture/restore

`knowledge_library.py` reads `PaperTopic`/`PaperConcept` for paper detail (lines ~338-343) and captures/restores them around re-ingest (`_capture_*`/`_restore_paper_links`, lines ~338-410). Move both to `grouping_links` (`anchor_type='paper'`).

**Files:** Modify `src/neurodb/api/routes/knowledge_library.py`; Test `tests/integration/test_knowledge_library_groupings.py` (new).

- [ ] **Step 1: Failing test** (new file) — seed a paper + a topic grouping + a `grouping_links(anchor_type='paper')`; GET the paper detail route; assert the response's topic links reflect the grouping link. (Inspect the actual paper-detail route name/path in `knowledge_library.py` and assert the field that previously came from `paper_topics`.)

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement** — in `src/neurodb/api/routes/knowledge_library.py`:
  - Paper-detail link reads (lines ~338-343): replace the `PaperTopic`/`PaperConcept` queries with engine reads:
    ```python
    from neurodb.db.grouping_store import get_groupings_for_anchor
    paper_groupings = get_groupings_for_anchor(session, "paper", paper_id)
    # split by g["type"] into topic/concept link dicts matching the existing response shape
    ```
  - Capture/restore (`_capture_paper_links` / `_restore_paper_links`, lines ~392-410): snapshot and restore `grouping_links` rows where `anchor_type='paper' AND anchor_id=paper_id` instead of `PaperTopic`/`PaperConcept`. Keep `DatasetPacketPaper` handling unchanged (it is not a topic/concept link). The capture deletes paper links before re-ingest and restore re-adds them; switch both to `GroupingLink` rows.
  - Any add-link endpoint that inserted `PaperTopic(**values)` → `link_grouping(session, grouping_id, "paper", paper_id, status="confirmed")`.
  - Drop now-unused `PaperTopic`/`PaperConcept` imports if nothing else references them.

> Read the full `_capture_paper_links`/`_restore_paper_links` pair before editing; preserve their exact call sites and return-shape contract (the route relies on the captured dict to restore after a destructive re-ingest). The migration must round-trip: capture → delete → restore yields the same `grouping_links`.

- [ ] **Step 4: Run** the new test + `uv run pytest tests/ -q -k knowledge` → PASS.
- [ ] **Step 5: Commit** `feat(groupings): knowledge library paper links via the engine`.

---

### Task 8: Study log — note topic/concept resolution + write

`study.py` `list_tags`/`search_tags` outerjoin `Topic`/`Concept` on `StudyNote.topic_id`/`concept_id` to resolve a note's anchor name. Resolve via `grouping_links(anchor_type='study_note')` instead, and write a grouping link when a note is anchored to a topic/concept.

**Files:** Modify `src/neurodb/study.py`; Test `tests/unit/test_study.py` (append/adjust).

- [ ] **Step 1: Failing test** — create a study note, attach it to a topic grouping via `link_grouping(g.id, "study_note", note.id)`, and assert `list_tags` resolves `source='topic'`, `source_id='<grouping name>'`. Mirror the existing study test fixtures.

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement** — in `src/neurodb/study.py`:
  - Add a resolver that, given a note id, returns its topic/concept grouping name from the engine:
    ```python
    def _note_grouping_anchor(session, note_id: int) -> tuple[str, str] | None:
        from neurodb.db.grouping_store import get_groupings_for_anchor
        gs = get_groupings_for_anchor(session, "study_note", note_id)
        for g in gs:  # prefer topic, then concept
            if g["type"] == "topic":
                return ("topic", g["name"])
        for g in gs:
            if g["type"] == "concept":
                return ("concept", g["name"])
        return None
    ```
  - In `list_tags` and `search_tags`, drop the `Topic`/`Concept` outerjoins; build rows from `StudyNote`/`DatasetIndex`/`Paper` only, and when `index_id`/`paper_id` are not the anchor, call `_note_grouping_anchor(session, note.id)` to fill `(source, source_id)`. Keep the index→paper precedence; topic/concept now come from the engine.
  - Where a note is created/anchored to a topic or concept (the write path that previously set `StudyNote.topic_id`/`concept_id`): after `session.flush()` on the note, also `link_grouping(session, grouping_id, "study_note", note.id, status="confirmed")`. (Find the call site that sets those columns; if note creation in this module never sets them, no write change is needed and the resolver alone suffices.)
  - Remove now-unused `Topic`/`Concept` imports if nothing else uses them.

> `_resolve_anchor`'s precedence is index → topic → concept → paper. Preserve that ordering when integrating `_note_grouping_anchor` so existing dataset/paper-anchored notes are unaffected.

- [ ] **Step 4: Run** `uv run pytest tests/unit/test_study.py -q` → PASS.
- [ ] **Step 5: Commit** `feat(groupings): study-log note anchors via the engine`.

---

### Task 9: LOG-064 — `delete_research_question` cleans grouping_links + orphan proposals

**Files:** Modify `src/neurodb/research_tools.py` (`delete_research_question`); Test `tests/unit/test_research_tools.py` or `tests/integration/test_question_link_routes.py` (append).

- [ ] **Step 1: Failing test** — append to `tests/integration/test_question_link_routes.py`:

```python
def test_delete_question_removes_grouping_links_and_orphan_proposals(client_engine):
    from sqlalchemy import text
    client, engine = client_engine
    qid = _make_question(engine)
    with Session(engine) as s:
        active = get_or_create_grouping(s, "topic", "stroke")            # shared/active
        prop = get_or_create_grouping(s, "concept", "engram", status="proposed")  # orphan-only
        link_grouping(s, active.id, "question", qid, status="confirmed")
        link_grouping(s, prop.id, "question", qid, status="pending")
        s.commit()
        active_id, prop_id = active.id, prop.id

    resp = client.delete(f"/api/research/questions/{qid}")
    assert resp.status_code == 204
    with engine.connect() as conn:
        links = conn.execute(text(
            "SELECT COUNT(*) FROM grouping_links WHERE anchor_type='question' AND anchor_id=:q"),
            {"q": qid}).scalar()
        prop_exists = conn.execute(text("SELECT COUNT(*) FROM groupings WHERE id=:i"),
                                   {"i": prop_id}).scalar()
        active_exists = conn.execute(text("SELECT COUNT(*) FROM groupings WHERE id=:i"),
                                     {"i": active_id}).scalar()
    assert links == 0          # question links gone
    assert prop_exists == 0    # orphan proposed grouping cleaned up
    assert active_exists == 1  # active grouping retained
```

- [ ] **Step 2: Run** → FAIL (delete still touches only legacy join tables).

- [ ] **Step 3: Implement** — replace the legacy cascade in `delete_research_question` (`research_tools.py:153-171`) with grouping_links cleanup + orphan-proposal removal:

```python
def delete_research_question(engine: Engine, question_id: int) -> dict:
    """Delete a question, its grouping links, and any now-orphan proposed groupings.
    Does not touch active groupings, hypotheses, or gaps."""
    from sqlalchemy import select as _select
    from neurodb.schema import GroupingLink, Grouping
    with get_session(engine) as session:
        row = session.get(ResearchQuestion, question_id)
        if row is None:
            return {"error": f"question {question_id} not found"}
        links = session.execute(
            _select(GroupingLink).where(
                GroupingLink.anchor_type == "question",
                GroupingLink.anchor_id == question_id,
            )
        ).scalars().all()
        affected_grouping_ids = {gl.grouping_id for gl in links}
        for gl in links:
            session.delete(gl)
        session.flush()
        # Remove proposed groupings left with no remaining links anywhere.
        for gid in affected_grouping_ids:
            g = session.get(Grouping, gid)
            if g is not None and g.status == "proposed":
                remaining = session.execute(
                    _select(GroupingLink).where(GroupingLink.grouping_id == gid)
                ).first()
                if remaining is None:
                    session.delete(g)
        session.delete(row)
        session.flush()
        return {"deleted": True}
```

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `fix(groupings): delete_research_question cleans grouping_links + orphans (LOG-064)`.

---

### Task 10: LOG-065 — independent per-topic collapse in `GroupingHierarchy`

**Files:** Modify `frontend/src/components/GroupingHierarchy.tsx`; Test `frontend/src/components/GroupingHierarchy.test.tsx` (append).

- [ ] **Step 1: Failing test** — append:

```tsx
  it('collapses a single top-level grouping independently', () => {
    render(<GroupingHierarchy type="topic" />, { wrapper: wrapperWith([PARENT, CHILD, LOOSE]) })
    // children visible initially
    expect(screen.getByLabelText('parent of neuroplasticity')).toBeTruthy()
    // collapse only "plasticity"
    fireEvent.click(screen.getByLabelText('toggle plasticity'))
    expect(screen.queryByLabelText('parent of neuroplasticity')).toBeNull()  // child hidden
    expect(screen.getByLabelText('parent of stroke')).toBeTruthy()           // other group unaffected
  })
```

- [ ] **Step 2: Run** `npm test -- src/components/GroupingHierarchy.test.tsx` → FAIL.

- [ ] **Step 3: Implement** — in `GroupingHierarchy.tsx`, add independent collapse state keyed by grouping id and a toggle control per top-level row:

```tsx
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({})
  const toggle = (id: number) =>
    setCollapsed(prev => ({ ...prev, [id]: !prev[id] }))
```
  In each top-level block, render a toggle button before the row and gate the children:
```tsx
        <div key={parent.id} style={{ marginBottom: 4 }}>
          <button
            type="button"
            aria-label={`toggle ${parent.name}`}
            onClick={() => toggle(parent.id)}
            style={{ fontSize: 10, marginRight: 4, border: 'none', background: 'transparent', cursor: 'pointer' }}
          >
            {collapsed[parent.id] ? '▸' : '▾'}
          </button>
          <GroupingRow g={parent} parents={eligibleParents(parent)}
            onReparent={(pid) => reparent.mutate({ id: parent.id, parentId: pid })} />
          {!collapsed[parent.id] && (
            <div style={{ marginLeft: 14 }}>
              {childrenOf(parent.id).map(child => (
                <GroupingRow key={child.id} g={child} parents={eligibleParents(child)}
                  onReparent={(pid) => reparent.mutate({ id: child.id, parentId: pid })} />
              ))}
            </div>
          )}
        </div>
```

- [ ] **Step 4: Run** → PASS (4 tests).
- [ ] **Step 5: Commit** `feat(ui/groupings): independent per-topic collapse in hierarchy view (LOG-065)`.

---

### Task 11: LOG-066 — suggestion auto-refresh after question create

After a successful create, briefly poll the question list so background-matcher chips appear without a manual refresh.

**Files:** Modify `frontend/src/pages/ResearchPanel.tsx`; Test `frontend/src/pages/ResearchPanel.test.tsx` (append).

- [ ] **Step 1: Failing test** — assert that creating a question triggers a bounded refetch. Simplest deterministic check: spy on `api.getResearchQuestionsDetail` and assert it is called again shortly after a create mutation resolves (use `vi.useFakeTimers()` + advance, or assert the create mutation's `onSuccess` invalidates `['research-questions-detail', …]`). Mirror the existing fetch-based test in the file.

```tsx
  it('refetches questions after create to surface async suggestions', async () => {
    const spy = vi.spyOn(api, 'getResearchQuestionsDetail').mockResolvedValue([])
    vi.spyOn(api, 'createQuestion').mockResolvedValue({
      id: 99, question: 'Q', status: 'open', topic_context: '', origin_session_id: null,
      created_at: '2026-06-02', topics: [], concepts: [],
    } as never)
    // render panel, submit the create form, then assert a follow-up refetch occurs
    // (advance fake timers if using an interval).
    // ... arrange/act ...
    await waitFor(() => expect(spy.mock.calls.length).toBeGreaterThan(1))
  })
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement** — in the create-question mutation's `onSuccess` in `ResearchPanel.tsx`, schedule a bounded poll that invalidates the questions query a few times then stops:

```tsx
  const POLL_MS = 2500
  const POLL_MAX = 6  // ~15s total
  const schedulePollForSuggestions = () => {
    let n = 0
    const t = setInterval(() => {
      n += 1
      queryClient.invalidateQueries({ queryKey: ['research-questions-detail'] })
      if (n >= POLL_MAX) clearInterval(t)
    }, POLL_MS)
  }
```
  Call `schedulePollForSuggestions()` in the create mutation's `onSuccess` (after the existing invalidate). Keep it simple; no refetch-until-populated needed.

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(ui/groupings): poll for async suggestions after create (LOG-066)`.

---

### Task 12: Full suites, manual test plan, status + log sync

**Files:** Create `docs/testsPlans/manualTestPlan_groupings_phase4.md`; Modify `docs/projectStatus.md`, `docs/testLog.md`.

- [ ] **Step 1: Backend suite** — `uv run pytest tests/ -q`. Pass: no new failures beyond `docs/testLog.md`. Fix any test that asserted the old `get_topic_bundle`/`get_question_bundle` shapes by repointing to the engine equivalents (do not weaken assertions).
- [ ] **Step 2: Frontend** — `cd frontend && npm test && npm run build`. Both green; remove any now-unused imports `tsc` flags.
- [ ] **Step 3: `git grep` legacy-readers check** — confirm only `schema.py`, the migrations in `db.py`, `topic_store.py` (dormant), and `ui/pages/*` (out of scope) still reference `PaperTopic`/`PaperConcept`/`TopicConcept`/`DatasetPacketTopic`/`QuestionTopic`/`QuestionConcept`/`get_topic_bundle`. No agent/route/store/research_tools reference should remain:
  ```bash
  git grep -nE "get_topic_bundle|PaperTopic|PaperConcept|TopicConcept|DatasetPacketTopic|QuestionTopic|QuestionConcept" -- src/neurodb | grep -vE "schema.py|/db.py$|topic_store.py|ui/pages/"
  ```
  Expected: empty.
- [ ] **Step 4: Manual test plan** — create `docs/testsPlans/manualTestPlan_groupings_phase4.md` covering, via the React app + live server: tutor "tag paper to topic" persists and shows in the hierarchy/filter; tutor/research bundles return engine data; knowledge-library paper detail shows topic/concept links; study log shows topic/concept-anchored notes; deleting a question removes its chips and any orphan proposals (LOG-064); hierarchy collapse is independent (LOG-065); suggestions appear without manual refresh (LOG-066). Prerequisites start with `uv run pytest tests/ -q` and `cd frontend && npm test`.
- [ ] **Step 5: Status + log sync** — in `docs/projectStatus.md`: set Active focus to "Unified Groupings Phase 4 complete — all consumers on the engine; legacy tables dormant pending Phase 5"; Next to "Unified Groupings Phase 5 — drop legacy topics/concepts + join tables once grep proves no references"; update the Research epoch row; mark this plan implemented and add the manual test plan to the reference table. In `docs/testLog.md`, move LOG-064, LOG-065, LOG-066 from Open to Resolved with resolution notes.
- [ ] **Step 6: Commit** `docs: Groupings Phase 4 manual plan; status + LOG-064/065/066 resolved`.

---

## Phase 4 Done When

- No agent, API route, store helper, or `research_tools` reads or writes the legacy `topics`/`concepts`/join tables (verified by the Task 12 grep); the only remaining references are `schema.py`, the migrations, dormant `topic_store.py`, and out-of-scope `ui/pages/*`.
- Bundles (`get_grouping_bundle`, `get_question_bundle`), claims, study-note resolution, focus resolution, paper detail, and tutor paper-tagging all run through `grouping_links`.
- LOG-064/065/066 are fixed and resolved.
- `uv run pytest tests/ -q` and `cd frontend && npm test && npm run build` are green.

## Out of Scope (Phase 5 / later)

- Dropping the legacy `topics`/`concepts` tables and the six join tables, and the vestigial `ResearchQuestion.topic_id` / `StudyNote.topic_id`/`concept_id` columns → **Phase 5**.
- Migrating the Streamlit `ui/pages/*` (deprecated; will read empty topic data post-Phase-5).
- Removing the now-dormant `topic_store.py` write/bundle helpers → Phase 5 cleanup.
