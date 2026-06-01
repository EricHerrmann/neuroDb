# Research Question Phase 1 — Capture & Categorize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire research questions as first-class DB objects: direct UI creation, agent-suggested multi-topic tagging (persisted as pending/confirmed), collapsible question list with badges and chips, and delete with cascade.

**Architecture:** Schema adds `question_topics` and `question_concepts` join tables with a `status` column (pending/confirmed) and an `origin_session_id` column on `research_questions`. Backend layers follow the established topic_store → research_tools → API schema → API route pattern. Topic extraction is a lightweight DB-side keyword match — no LLM call — fired inline by the agent and as a background thread from the API POST route. The React UI extends `ResearchPanel.tsx` with a creation form, inline chips, and a filter bar.

**Tech Stack:** Python, SQLAlchemy ORM, DuckDB (prod) / SQLite (tests), FastAPI, React 18, TypeScript, @tanstack/react-query

---

## File Map

| File | Change |
|---|---|
| `src/neurodb/schema.py` | Add `QuestionTopic`, `QuestionConcept` ORM models; add `origin_session_id` column to `ResearchQuestion` |
| `src/neurodb/db.py` | Add `_migration_016_question_topic_tables` and register it in `_MIGRATIONS` |
| `src/neurodb/db/topic_store.py` | Add `link_question_topic`, `update_question_topic_status`, `unlink_question_topic`, `link_question_concept`, `update_question_concept_status`, `unlink_question_concept`, `extract_question_topics` |
| `src/neurodb/research_tools.py` | Add `create_research_question`, `update_research_question`, `delete_research_question` |
| `src/neurodb/api/schemas/research.py` | Add `QuestionTopicLink`, `QuestionConceptLink`, `ResearchQuestionDetail`, `CreateQuestionRequest`, `UpdateQuestionRequest`, `AddTopicLinkRequest`, `PatchLinkStatusRequest`, `AddConceptLinkRequest` |
| `src/neurodb/api/routes/research.py` | Add 10 new routes: POST/PUT/DELETE question; GET detail; POST/PATCH/DELETE topics; POST/PATCH/DELETE concepts; extend GET list |
| `src/neurodb/agents/research_agent.py` | Add `extract_question_topics` tool definition; add handler in `_execute_tool_block`; call it after `record_research_question` |
| `frontend/src/api/types.ts` | Add `QuestionTopicLink`, `QuestionConceptLink`, `ResearchQuestionDetail`, `CreateQuestionRequest` |
| `frontend/src/api/client.ts` | Add `createQuestion`, `updateQuestion`, `deleteQuestion`, `getQuestionDetail`, `getResearchQuestionsWithLinks`, `addQuestionTopic`, `confirmQuestionTopic`, `removeQuestionTopic`, `addQuestionConcept`, `confirmQuestionConcept`, `removeQuestionConcept` |
| `frontend/src/pages/ResearchPanel.tsx` | Add question creation form; extend question list with collapsible, topic badges, pending chips, delete action, topic filter |
| `tests/unit/test_question_topic_store.py` | New — T1 (question_topics CRUD), T2 (question_concepts CRUD) |
| `tests/unit/test_question_migration_016.py` | New — T3 (migration backfill) |
| `tests/unit/test_extract_question_topics.py` | New — T4 (extract_question_topics) |
| `tests/unit/test_api_research_phase1.py` | New — T5 (delete cascade), T7 (idempotency) |
| `tests/integration/test_question_phase1.py` | New — T6 (create → suggest → confirm → filter) |

---

## Task 1: Write Manual Test Plan

**Files:**
- Create: `docs/testsPlans/manualTestPlan_research_question_phase1.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Create the manual test plan**

Create `docs/testsPlans/manualTestPlan_research_question_phase1.md` with this content:

```markdown
# Manual Test Plan — Research Question Phase 1: Capture & Categorize

**Phase:** Research Question Phase 1
**Spec:** `docs/superpowers/specs/2026-06-01-research-question-phase1-design.md`
**Status:** Not started

---

## Prerequisites

- [ ] Run automated tests: `uv run pytest tests/ -q`
  Pass criterion: no new failures beyond those tracked in `docs/testLog.md`.
- [ ] Start the dev server: `uv run neurodb serve` (backend) + `cd frontend && npm run dev`

---

## T1 — Create a question from the UI

**Steps:**
1. Open ResearchPanel.
2. Fill in the question text area with: "Do biological memory systems and transformer attention share a common retrieval mechanism?"
3. Optionally fill topic_context with: "neuroscience and AI convergence".
4. Click Submit.

**Pass criteria:**
- Question appears in the question list immediately with status `open`.
- Within a few seconds, pending topic/concept suggestion chips appear below the question row.
- No page spinner or error toast.

---

## T2 — Confirm a suggested topic chip

**Steps:**
1. After T1, locate a pending topic chip on the question row.
2. Click "Confirm" on the chip.

**Pass criteria:**
- The chip is replaced by a confirmed topic badge.
- `GET /api/research/questions/{id}` (via browser DevTools or SQL panel) shows the topic with status `confirmed`.

---

## T3 — Dismiss a suggested topic chip

**Steps:**
1. After T1, locate a pending topic chip on the question row.
2. Click "Dismiss" on the chip.

**Pass criteria:**
- The chip disappears from the row.
- The topic no longer appears in the question's topic list.

---

## T4 — Filter question list by topic

**Steps:**
1. Confirm at least one topic on a question (T2).
2. Select that topic in the topic filter bar.

**Pass criteria:**
- Only questions with that confirmed topic are shown.
- Removing the filter restores all questions.

---

## T5 — Collapse and expand the question list

**Steps:**
1. Click "Collapse" on the Questions section header.
2. Click "Expand".

**Pass criteria:**
- Questions section collapses and the list disappears.
- Expanding restores all rows.
- State does not persist across page reload (local component state only).

---

## T6 — Delete a question

**Steps:**
1. Click the Delete control on any question row.
2. Confirm the prompt.

**Pass criteria:**
- Confirmation prompt appears before deletion.
- Question is removed from the list after confirmation.
- `GET /api/research/questions/{id}` returns 404.
- Cancelling the prompt leaves the question in place.
```

- [ ] **Step 2: Add plan to projectStatus.md active plans table**

In `docs/projectStatus.md`, add this row to the Active Plans / Specs table:

```
| `docs/testsPlans/manualTestPlan_research_question_phase1.md` | Research Question Phase 1 manual test plan — M1-M6 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/testsPlans/manualTestPlan_research_question_phase1.md docs/projectStatus.md
git commit -m "docs: add Research Question Phase 1 manual test plan"
```

---

## Task 2: ORM Models — QuestionTopic and QuestionConcept

**Files:**
- Modify: `src/neurodb/schema.py`
- Create: `tests/unit/test_question_topic_store.py`

- [ ] **Step 1: Write failing tests for T1 and T2**

Create `tests/unit/test_question_topic_store.py`:

```python
"""Unit tests for question_topics and question_concepts join table CRUD (T1, T2)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Concept, QuestionConcept, QuestionTopic, ResearchQuestion, Topic


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def seed(engine):
    """Returns (question_id, topic_id, concept_id)."""
    with Session(engine) as session:
        q = ResearchQuestion(
            question="Test question?",
            topic_context="",
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(q)
        t = Topic(name="plasticity", description=None, status="active",
                  created_at=_now(), updated_at=_now())
        session.add(t)
        c = Concept(name="LTP", description=None, status="active",
                    created_at=_now(), updated_at=_now())
        session.add(c)
        session.flush()
        yield q.id, t.id, c.id


# --- T1: question_topics ---

def test_question_topic_insert_and_read(engine, seed):
    q_id, t_id, _ = seed
    with Session(engine) as session:
        row = QuestionTopic(question_id=q_id, topic_id=t_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        fetched = session.execute(
            select(QuestionTopic).where(
                QuestionTopic.question_id == q_id,
                QuestionTopic.topic_id == t_id,
            )
        ).scalar_one()
        assert fetched.status == "pending"


def test_question_topic_confirm(engine, seed):
    q_id, t_id, _ = seed
    with Session(engine) as session:
        row = QuestionTopic(question_id=q_id, topic_id=t_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        row.status = "confirmed"
        session.flush()
        fetched = session.execute(
            select(QuestionTopic).where(
                QuestionTopic.question_id == q_id,
                QuestionTopic.topic_id == t_id,
            )
        ).scalar_one()
        assert fetched.status == "confirmed"


def test_question_topic_dismiss_deletes_row(engine, seed):
    q_id, t_id, _ = seed
    with Session(engine) as session:
        row = QuestionTopic(question_id=q_id, topic_id=t_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        session.delete(row)
        session.flush()
        result = session.execute(
            select(QuestionTopic).where(
                QuestionTopic.question_id == q_id,
                QuestionTopic.topic_id == t_id,
            )
        ).scalar_one_or_none()
        assert result is None


def test_question_topic_unique_constraint(engine, seed):
    q_id, t_id, _ = seed
    with Session(engine) as session:
        session.add(QuestionTopic(question_id=q_id, topic_id=t_id, status="pending", created_at=_now()))
        session.flush()
        session.add(QuestionTopic(question_id=q_id, topic_id=t_id, status="confirmed", created_at=_now()))
        with pytest.raises(IntegrityError):
            session.flush()


# --- T2: question_concepts ---

def test_question_concept_insert_and_read(engine, seed):
    q_id, _, c_id = seed
    with Session(engine) as session:
        row = QuestionConcept(question_id=q_id, concept_id=c_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        fetched = session.execute(
            select(QuestionConcept).where(
                QuestionConcept.question_id == q_id,
                QuestionConcept.concept_id == c_id,
            )
        ).scalar_one()
        assert fetched.status == "pending"


def test_question_concept_confirm(engine, seed):
    q_id, _, c_id = seed
    with Session(engine) as session:
        row = QuestionConcept(question_id=q_id, concept_id=c_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        row.status = "confirmed"
        session.flush()
        fetched = session.execute(
            select(QuestionConcept).where(
                QuestionConcept.question_id == q_id,
                QuestionConcept.concept_id == c_id,
            )
        ).scalar_one()
        assert fetched.status == "confirmed"


def test_question_concept_dismiss_deletes_row(engine, seed):
    q_id, _, c_id = seed
    with Session(engine) as session:
        row = QuestionConcept(question_id=q_id, concept_id=c_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        session.delete(row)
        session.flush()
        result = session.execute(
            select(QuestionConcept).where(
                QuestionConcept.question_id == q_id,
                QuestionConcept.concept_id == c_id,
            )
        ).scalar_one_or_none()
        assert result is None


def test_question_concept_unique_constraint(engine, seed):
    q_id, _, c_id = seed
    with Session(engine) as session:
        session.add(QuestionConcept(question_id=q_id, concept_id=c_id, status="pending", created_at=_now()))
        session.flush()
        session.add(QuestionConcept(question_id=q_id, concept_id=c_id, status="confirmed", created_at=_now()))
        with pytest.raises(IntegrityError):
            session.flush()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_question_topic_store.py -v
```

Expected: `ImportError` — `QuestionTopic` and `QuestionConcept` not yet defined.

- [ ] **Step 3: Add ORM models to schema.py**

At the end of `src/neurodb/schema.py`, before the `KnowledgeGrowthSnapshot` class, add:

```python
class QuestionTopic(Base):
    """Many-to-many: research_questions ↔ topics, with pending/confirmed lifecycle."""
    __tablename__ = "question_topics"
    __table_args__ = (
        UniqueConstraint("question_id", "topic_id", name="uq_question_topic"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("question_topics_id_seq"), primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class QuestionConcept(Base):
    """Many-to-many: research_questions ↔ concepts, with pending/confirmed lifecycle."""
    __tablename__ = "question_concepts"
    __table_args__ = (
        UniqueConstraint("question_id", "concept_id", name="uq_question_concept"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("question_concepts_id_seq"), primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    concept_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

Also add `origin_session_id` to the existing `ResearchQuestion` class (after the `topic_id` line):

```python
    origin_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_question_topic_store.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_question_topic_store.py
git commit -m "feat: add QuestionTopic, QuestionConcept ORM models and origin_session_id column"
```

---

## Task 3: Migration 016

**Files:**
- Modify: `src/neurodb/db.py`
- Create: `tests/unit/test_question_migration_016.py`

- [ ] **Step 1: Write failing test for T3**

Create `tests/unit/test_question_migration_016.py`:

```python
"""Unit test for migration 016 — question_topics/question_concepts tables and backfill (T3)."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, ResearchQuestion, Topic
from neurodb.db import _migration_016_question_topic_tables


def _now():
    return datetime.now(timezone.utc).isoformat()


def _make_engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


def test_migration_creates_tables():
    engine = _make_engine()
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='question_topics'"
        )).fetchone()
        assert row is not None, "question_topics table not created"
        row = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='question_concepts'"
        )).fetchone()
        assert row is not None, "question_concepts table not created"


def test_migration_adds_origin_session_id():
    engine = _make_engine()
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()
    with engine.connect() as conn:
        # Can insert with origin_session_id without error
        conn.execute(text(
            "INSERT INTO research_questions "
            "(question, topic_context, status, created_at, updated_at, origin_session_id) "
            "VALUES ('q?', '', 'open', :now, :now, NULL)"
        ), {"now": _now()})
        conn.commit()


def test_migration_backfills_existing_topic_id():
    engine = _make_engine()
    # Insert a topic and a question with topic_id set
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO topics (name, status, created_at, updated_at) VALUES ('plasticity', 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        topic_id = conn.execute(text("SELECT id FROM topics WHERE name='plasticity'")).fetchone()[0]
        conn.execute(text(
            "INSERT INTO research_questions "
            "(question, topic_context, status, created_at, updated_at, topic_id) "
            "VALUES ('q?', '', 'open', :now, :now, :tid)"
        ), {"now": _now(), "tid": topic_id})
        conn.commit()
    with engine.connect() as conn:
        q_id = conn.execute(text("SELECT id FROM research_questions WHERE question='q?'")).fetchone()[0]
    # Apply migration
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()
    # Check backfill
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT status FROM question_topics WHERE question_id=:qid AND topic_id=:tid"
        ), {"qid": q_id, "tid": topic_id}).fetchone()
        assert row is not None, "backfill row not created"
        assert row[0] == "confirmed", f"expected 'confirmed', got {row[0]}"


def test_migration_is_idempotent():
    engine = _make_engine()
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()
    # Running twice should not raise
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()


def test_existing_topic_id_fk_preserved():
    engine = _make_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO topics (name, status, created_at, updated_at) VALUES ('plasticity', 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        topic_id = conn.execute(text("SELECT id FROM topics WHERE name='plasticity'")).fetchone()[0]
        conn.execute(text(
            "INSERT INTO research_questions "
            "(question, topic_context, status, created_at, updated_at, topic_id) "
            "VALUES ('q?', '', 'open', :now, :now, :tid)"
        ), {"now": _now(), "tid": topic_id})
        conn.commit()
    with engine.connect() as conn:
        _migration_016_question_topic_tables(conn)
        conn.commit()
    # topic_id column still exists and has value
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT topic_id FROM research_questions WHERE question='q?'"
        )).fetchone()
        assert row[0] == topic_id, "topic_id FK was removed or cleared"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_question_migration_016.py -v
```

Expected: `ImportError` — `_migration_016_question_topic_tables` not yet defined.

- [ ] **Step 3: Add migration function to db.py**

In `src/neurodb/db.py`, add this function before `_MIGRATIONS`:

```python
def _migration_016_question_topic_tables(conn) -> None:
    """Create question_topics and question_concepts join tables; add origin_session_id to research_questions."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS question_topics (
            id INTEGER PRIMARY KEY,
            question_id INTEGER NOT NULL,
            topic_id INTEGER NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at VARCHAR(32) NOT NULL
        )
    """))
    try:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_question_topic "
            "ON question_topics (question_id, topic_id)"
        ))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_question_topics_question_id "
        "ON question_topics (question_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_question_topics_status "
        "ON question_topics (status)"
    ))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS question_concepts (
            id INTEGER PRIMARY KEY,
            question_id INTEGER NOT NULL,
            concept_id INTEGER NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at VARCHAR(32) NOT NULL
        )
    """))
    try:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_question_concept "
            "ON question_concepts (question_id, concept_id)"
        ))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_question_concepts_question_id "
        "ON question_concepts (question_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_question_concepts_status "
        "ON question_concepts (status)"
    ))

    try:
        conn.execute(text("ALTER TABLE research_questions ADD COLUMN origin_session_id INTEGER"))
    except Exception:
        pass  # column already exists

    # Backfill question_topics from existing non-null topic_id rows
    try:
        conn.execute(text("""
            INSERT INTO question_topics (question_id, topic_id, status, created_at)
            SELECT id, topic_id, 'confirmed', created_at
            FROM research_questions
            WHERE topic_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM question_topics qt
                WHERE qt.question_id = research_questions.id
                  AND qt.topic_id = research_questions.topic_id
              )
        """))
    except Exception:
        pass  # backfill already applied or table was empty
```

Add `16: _migration_016_question_topic_tables` to `_MIGRATIONS`:

```python
_MIGRATIONS: dict[int, callable] = {
    ...
    15: _migration_015_model_call_log_context_counts,
    16: _migration_016_question_topic_tables,
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_question_migration_016.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
uv run pytest tests/ -q
```

Expected: same pass/fail count as before this task.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/db.py tests/unit/test_question_migration_016.py
git commit -m "feat: add migration 016 — question_topics/question_concepts tables and backfill"
```

---

## Task 4: DB Helpers — topic_store.py + extract_question_topics

**Files:**
- Modify: `src/neurodb/db/topic_store.py`
- Create: `tests/unit/test_extract_question_topics.py`

- [ ] **Step 1: Write failing test for T4**

Create `tests/unit/test_extract_question_topics.py`:

```python
"""Unit test for extract_question_topics — keyword matching and pending row persistence (T4)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Concept, QuestionConcept, QuestionTopic, ResearchQuestion, Topic
from neurodb.db.topic_store import extract_question_topics


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def seeded(engine):
    """Returns (question_id, topic_id, concept_id). Topic='plasticity', concept='LTP'."""
    with Session(engine) as session:
        t = Topic(name="plasticity", description=None, status="active",
                  created_at=_now(), updated_at=_now())
        c = Concept(name="LTP", description=None, status="active",
                    created_at=_now(), updated_at=_now())
        q = ResearchQuestion(
            question="Does plasticity involve LTP mechanisms?",
            topic_context="",
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add_all([t, c, q])
        session.flush()
        yield q.id, t.id, c.id


def test_extract_matches_and_persists_pending_rows(engine, seeded):
    q_id, t_id, c_id = seeded
    with Session(engine) as session:
        result = extract_question_topics(session, q_id, "Does plasticity involve LTP mechanisms?")
        session.flush()
        assert "plasticity" in result["suggested_topics"]
        assert "LTP" in result["suggested_concepts"]
        qt = session.execute(
            select(QuestionTopic).where(
                QuestionTopic.question_id == q_id,
                QuestionTopic.topic_id == t_id,
            )
        ).scalar_one_or_none()
        assert qt is not None
        assert qt.status == "pending"
        qc = session.execute(
            select(QuestionConcept).where(
                QuestionConcept.question_id == q_id,
                QuestionConcept.concept_id == c_id,
            )
        ).scalar_one_or_none()
        assert qc is not None
        assert qc.status == "pending"


def test_extract_returns_empty_when_no_match(engine, seeded):
    q_id, _, _ = seeded
    with Session(engine) as session:
        result = extract_question_topics(session, q_id, "completely unrelated question about clouds")
        session.flush()
        assert result["suggested_topics"] == []
        assert result["suggested_concepts"] == []


def test_extract_does_not_create_duplicate_rows(engine, seeded):
    q_id, t_id, c_id = seeded
    with Session(engine) as session:
        extract_question_topics(session, q_id, "Does plasticity involve LTP mechanisms?")
        session.flush()
        # Call again — should not raise or duplicate
        extract_question_topics(session, q_id, "Does plasticity involve LTP mechanisms?")
        session.flush()
        count = session.execute(
            select(QuestionTopic).where(QuestionTopic.question_id == q_id)
        ).scalars().all()
        assert len(count) == 1, "expected exactly one QuestionTopic row"


def test_extract_does_not_create_new_topics(engine, seeded):
    q_id, _, _ = seeded
    with Session(engine) as session:
        before = len(session.execute(select(Topic)).scalars().all())
        extract_question_topics(session, q_id, "some brand new topic that does not exist")
        session.flush()
        after = len(session.execute(select(Topic)).scalars().all())
        assert before == after, "extract_question_topics must not create new topics"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_extract_question_topics.py -v
```

Expected: `ImportError` — `extract_question_topics` not yet defined.

- [ ] **Step 3: Add helpers to topic_store.py**

Append the following to `src/neurodb/db/topic_store.py` (after the existing imports, add `QuestionConcept` and `QuestionTopic` to the import from `neurodb.schema`; then add the new functions):

At the top, extend the `from neurodb.schema import (...)` block to include `QuestionConcept, QuestionTopic`.

Then add these functions at the end of the file:

```python
def link_question_topic(session: Session, question_id: int, topic_id: int, status: str = "confirmed") -> None:
    """Create a question→topic link. Skips if the link already exists."""
    exists = session.execute(
        select(QuestionTopic).where(
            QuestionTopic.question_id == question_id,
            QuestionTopic.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(QuestionTopic(
            question_id=question_id,
            topic_id=topic_id,
            status=status,
            created_at=_now(),
        ))
        session.flush()


def update_question_topic_status(session: Session, question_id: int, topic_id: int, status: str) -> bool:
    """Update status on an existing question→topic link. Returns True if found."""
    row = session.execute(
        select(QuestionTopic).where(
            QuestionTopic.question_id == question_id,
            QuestionTopic.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    row.status = status
    session.flush()
    return True


def unlink_question_topic(session: Session, question_id: int, topic_id: int) -> bool:
    """Delete a question→topic link. Returns True if found."""
    row = session.execute(
        select(QuestionTopic).where(
            QuestionTopic.question_id == question_id,
            QuestionTopic.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def link_question_concept(session: Session, question_id: int, concept_id: int, status: str = "confirmed") -> None:
    """Create a question→concept link. Skips if the link already exists."""
    exists = session.execute(
        select(QuestionConcept).where(
            QuestionConcept.question_id == question_id,
            QuestionConcept.concept_id == concept_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(QuestionConcept(
            question_id=question_id,
            concept_id=concept_id,
            status=status,
            created_at=_now(),
        ))
        session.flush()


def update_question_concept_status(session: Session, question_id: int, concept_id: int, status: str) -> bool:
    """Update status on an existing question→concept link. Returns True if found."""
    row = session.execute(
        select(QuestionConcept).where(
            QuestionConcept.question_id == question_id,
            QuestionConcept.concept_id == concept_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    row.status = status
    session.flush()
    return True


def unlink_question_concept(session: Session, question_id: int, concept_id: int) -> bool:
    """Delete a question→concept link. Returns True if found."""
    row = session.execute(
        select(QuestionConcept).where(
            QuestionConcept.question_id == question_id,
            QuestionConcept.concept_id == concept_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def extract_question_topics(session: Session, question_id: int, question_text: str) -> dict:
    """Match question text against existing topics/concepts; persist pending rows. Does not create new topics."""
    question_lower = question_text.lower()

    all_topics = session.execute(
        select(Topic).where(Topic.status == "active")
    ).scalars().all()
    suggested_topics = []
    for topic in all_topics:
        if topic.name.lower() in question_lower:
            existing = session.execute(
                select(QuestionTopic).where(
                    QuestionTopic.question_id == question_id,
                    QuestionTopic.topic_id == topic.id,
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(QuestionTopic(
                    question_id=question_id,
                    topic_id=topic.id,
                    status="pending",
                    created_at=_now(),
                ))
                suggested_topics.append(topic.name)

    all_concepts = session.execute(
        select(Concept).where(Concept.status == "active")
    ).scalars().all()
    suggested_concepts = []
    for concept in all_concepts:
        if concept.name.lower() in question_lower:
            existing = session.execute(
                select(QuestionConcept).where(
                    QuestionConcept.question_id == question_id,
                    QuestionConcept.concept_id == concept.id,
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(QuestionConcept(
                    question_id=question_id,
                    concept_id=concept.id,
                    status="pending",
                    created_at=_now(),
                ))
                suggested_concepts.append(concept.name)

    session.flush()
    return {
        "question_id": question_id,
        "suggested_topics": suggested_topics,
        "suggested_concepts": suggested_concepts,
    }
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_extract_question_topics.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db/topic_store.py tests/unit/test_extract_question_topics.py
git commit -m "feat: add question-topic/concept helpers and extract_question_topics to topic_store"
```

---

## Task 5: Research Tools — create / update / delete

**Files:**
- Modify: `src/neurodb/research_tools.py`
- Create: `tests/unit/test_api_research_phase1.py`

- [ ] **Step 1: Write failing tests for T5 and T7**

Create `tests/unit/test_api_research_phase1.py`:

```python
"""API-level tests for Phase 1 question routes — T5 (delete cascade), T7 (idempotency)."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base, Concept, QuestionConcept, QuestionTopic, ResearchQuestion, Topic


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def client_and_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return TestClient(app), engine


def _seed_question_with_links(engine):
    with Session(engine) as session:
        t = Topic(name="plasticity", description=None, status="active",
                  created_at=_now(), updated_at=_now())
        c = Concept(name="LTP", description=None, status="active",
                    created_at=_now(), updated_at=_now())
        q = ResearchQuestion(
            question="Test?", topic_context="", status="open",
            created_at=_now(), updated_at=_now(),
        )
        session.add_all([t, c, q])
        session.flush()
        session.add(QuestionTopic(question_id=q.id, topic_id=t.id, status="confirmed", created_at=_now()))
        session.add(QuestionConcept(question_id=q.id, concept_id=c.id, status="pending", created_at=_now()))
        session.flush()
        return q.id, t.id, c.id


# --- T5: delete cascade ---

def test_delete_question_returns_204(client_and_engine):
    client, engine = client_and_engine
    q_id, _, _ = _seed_question_with_links(engine)
    resp = client.delete(f"/api/research/questions/{q_id}")
    assert resp.status_code == 204


def test_delete_question_removes_join_rows(client_and_engine):
    client, engine = client_and_engine
    q_id, t_id, c_id = _seed_question_with_links(engine)
    client.delete(f"/api/research/questions/{q_id}")
    with Session(engine) as session:
        qt = session.execute(
            select(QuestionTopic).where(QuestionTopic.question_id == q_id)
        ).scalars().all()
        qc = session.execute(
            select(QuestionConcept).where(QuestionConcept.question_id == q_id)
        ).scalars().all()
        assert len(qt) == 0, "question_topics rows not deleted"
        assert len(qc) == 0, "question_concepts rows not deleted"


def test_delete_question_does_not_remove_topics_or_concepts(client_and_engine):
    client, engine = client_and_engine
    q_id, t_id, c_id = _seed_question_with_links(engine)
    client.delete(f"/api/research/questions/{q_id}")
    with Session(engine) as session:
        assert session.get(Topic, t_id) is not None, "Topic was incorrectly deleted"
        assert session.get(Concept, c_id) is not None, "Concept was incorrectly deleted"


def test_delete_question_404_when_not_found(client_and_engine):
    client, _ = client_and_engine
    resp = client.delete("/api/research/questions/99999")
    assert resp.status_code == 404


def test_deleted_question_returns_404_on_get(client_and_engine):
    client, engine = client_and_engine
    q_id, _, _ = _seed_question_with_links(engine)
    client.delete(f"/api/research/questions/{q_id}")
    resp = client.get(f"/api/research/questions/{q_id}")
    assert resp.status_code == 404


# --- T7: idempotency / unique constraint ---

def test_add_topic_link_twice_does_not_duplicate(client_and_engine):
    client, engine = client_and_engine
    with Session(engine) as session:
        t = Topic(name="memory", description=None, status="active",
                  created_at=_now(), updated_at=_now())
        q = ResearchQuestion(
            question="Test?", topic_context="", status="open",
            created_at=_now(), updated_at=_now(),
        )
        session.add_all([t, q])
        session.flush()
        q_id, t_id = q.id, t.id
    resp1 = client.post(f"/api/research/questions/{q_id}/topics", json={"topic_id": t_id})
    assert resp1.status_code == 200
    resp2 = client.post(f"/api/research/questions/{q_id}/topics", json={"topic_id": t_id})
    # Second call is idempotent — no 409 or 500
    assert resp2.status_code in (200, 204)
    with Session(engine) as session:
        rows = session.execute(
            select(QuestionTopic).where(
                QuestionTopic.question_id == q_id,
                QuestionTopic.topic_id == t_id,
            )
        ).scalars().all()
        assert len(rows) == 1, f"expected 1 row, got {len(rows)}"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_api_research_phase1.py -v
```

Expected: failures — new routes not yet defined.

- [ ] **Step 3: Add create / update / delete to research_tools.py**

Add these three functions to `src/neurodb/research_tools.py` (after `record_research_question`):

```python
def create_research_question(
    engine: Engine,
    question: str,
    topic_context: str | None = None,
    origin_session_id: int | None = None,
    now: str | None = None,
) -> dict:
    """Create a research question from the UI (not via agent chat)."""
    cleaned = question.strip()
    if not cleaned:
        return {"error": "question is required"}
    timestamp = now or _now_iso()
    with get_session(engine) as session:
        row = ResearchQuestion(
            question=cleaned,
            topic_context=(topic_context or "").strip(),
            status="open",
            origin_session_id=origin_session_id,
            created_at=timestamp,
            updated_at=timestamp,
        )
        session.add(row)
        session.flush()
        return {"id": row.id, "question": row.question, "status": row.status}


def update_research_question(
    engine: Engine,
    question_id: int,
    question: str | None = None,
    topic_context: str | None = None,
    now: str | None = None,
) -> dict:
    """Edit question text and/or topic_context."""
    with get_session(engine) as session:
        row = session.get(ResearchQuestion, question_id)
        if row is None:
            return {"error": f"question {question_id} not found"}
        if question is not None:
            cleaned = question.strip()
            if not cleaned:
                return {"error": "question is required"}
            row.question = cleaned
        if topic_context is not None:
            row.topic_context = topic_context.strip()
        row.updated_at = now or _now_iso()
        session.flush()
        return {"id": row.id, "question": row.question, "status": row.status}


def delete_research_question(engine: Engine, question_id: int) -> dict:
    """Delete a question and cascade join rows. Does not touch topics, concepts, hypotheses, or gaps."""
    from neurodb.schema import QuestionConcept, QuestionTopic
    with get_session(engine) as session:
        row = session.get(ResearchQuestion, question_id)
        if row is None:
            return {"error": f"question {question_id} not found"}
        # Cascade join rows
        for qt in session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(QuestionTopic).where(
                QuestionTopic.question_id == question_id
            )
        ).scalars().all():
            session.delete(qt)
        for qc in session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(QuestionConcept).where(
                QuestionConcept.question_id == question_id
            )
        ).scalars().all():
            session.delete(qc)
        session.delete(row)
        session.flush()
        return {"deleted": True}
```

> **Note:** The `__import__` trick avoids a circular import at module load time. A cleaner alternative is to add `from sqlalchemy import select as _select` at the top of the function body.

Replace those `__import__` calls with this cleaner version:

```python
def delete_research_question(engine: Engine, question_id: int) -> dict:
    """Delete a question and cascade join rows. Does not touch topics, concepts, hypotheses, or gaps."""
    from sqlalchemy import select as _select
    from neurodb.schema import QuestionConcept, QuestionTopic
    with get_session(engine) as session:
        row = session.get(ResearchQuestion, question_id)
        if row is None:
            return {"error": f"question {question_id} not found"}
        for qt in session.execute(
            _select(QuestionTopic).where(QuestionTopic.question_id == question_id)
        ).scalars().all():
            session.delete(qt)
        for qc in session.execute(
            _select(QuestionConcept).where(QuestionConcept.question_id == question_id)
        ).scalars().all():
            session.delete(qc)
        session.delete(row)
        session.flush()
        return {"deleted": True}
```

- [ ] **Step 4: Commit intermediate work (tools only)**

```bash
git add src/neurodb/research_tools.py
git commit -m "feat: add create/update/delete research question to research_tools"
```

---

## Task 6: API Schemas + Routes

**Files:**
- Modify: `src/neurodb/api/schemas/research.py`
- Modify: `src/neurodb/api/routes/research.py`
- Create: `tests/integration/test_question_phase1.py`

- [ ] **Step 1: Write failing integration test for T6**

Create `tests/integration/test_question_phase1.py`:

```python
"""Integration test T6: create question → confirm topic → filter by topic."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base, Concept, QuestionTopic, ResearchQuestion, Topic


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def client_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return TestClient(app), engine


def _seed_topic(engine, name: str) -> int:
    with Session(engine) as session:
        t = Topic(name=name, description=None, status="active",
                  created_at=_now(), updated_at=_now())
        session.add(t)
        session.flush()
        return t.id


def test_create_then_confirm_topic_then_filter(client_engine):
    client, engine = client_engine

    topic_id = _seed_topic(engine, "plasticity")

    # Create question via API — suppress background extraction thread
    with patch("threading.Thread"):
        resp = client.post("/api/research/questions", json={
            "question": "How does plasticity shape memory circuits?",
            "topic_context": "neuroscience",
        })
    assert resp.status_code == 200
    q_id = resp.json()["id"]

    # Add a pending topic link manually (simulates what the background extraction would create)
    with Session(engine) as session:
        session.add(QuestionTopic(
            question_id=q_id, topic_id=topic_id,
            status="pending", created_at=_now(),
        ))
        session.flush()

    # Confirm the topic link via PATCH
    resp = client.patch(f"/api/research/questions/{q_id}/topics/{topic_id}", json={"status": "confirmed"})
    assert resp.status_code == 200

    # GET detail — should show confirmed topic
    resp = client.get(f"/api/research/questions/{q_id}")
    assert resp.status_code == 200
    data = resp.json()
    confirmed = [t for t in data["topics"] if t["status"] == "confirmed"]
    assert any(t["topic_id"] == topic_id for t in confirmed), "confirmed topic not in detail response"

    # Filter list by topic — should return this question
    resp = client.get(f"/api/research/questions?topic_id={topic_id}")
    assert resp.status_code == 200
    ids = [q["id"] for q in resp.json()]
    assert q_id in ids, f"question {q_id} not returned when filtering by topic {topic_id}"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest tests/integration/test_question_phase1.py -v
```

Expected: failures — new routes not yet defined.

- [ ] **Step 3: Add new Pydantic schemas to api/schemas/research.py**

Append to `src/neurodb/api/schemas/research.py`:

```python
class QuestionTopicLink(BaseModel):
    topic_id: int
    topic_name: str
    status: str


class QuestionConceptLink(BaseModel):
    concept_id: int
    concept_name: str
    status: str


class ResearchQuestionDetail(BaseModel):
    id: int
    question: str
    status: str
    topic_context: str | None = None
    origin_session_id: int | None = None
    created_at: datetime | None = None
    topics: list[QuestionTopicLink] = []
    concepts: list[QuestionConceptLink] = []


class CreateQuestionRequest(BaseModel):
    question: str
    topic_context: str | None = None
    origin_session_id: int | None = None


class UpdateQuestionRequest(BaseModel):
    question: str | None = None
    topic_context: str | None = None


class AddTopicLinkRequest(BaseModel):
    topic_id: int


class PatchLinkStatusRequest(BaseModel):
    status: str


class AddConceptLinkRequest(BaseModel):
    concept_id: int
```

- [ ] **Step 4: Add new routes to api/routes/research.py**

At the top of `src/neurodb/api/routes/research.py`, extend the import from `neurodb.api.schemas.research` to include:

```python
from neurodb.api.schemas.research import (
    AddConceptLinkRequest,
    AddTopicLinkRequest,
    ClaimItem,
    CreateQuestionRequest,
    EvidenceLinkItem,
    Hypothesis,
    HypothesisReviewItem,
    PatchLinkStatusRequest,
    ResearchGapItem,
    ResearchQuestion,
    ResearchQuestionDetail,
    UpdateQuestionRequest,
)
```

Add a private helper function (before the route definitions):

```python
def _question_detail(engine: Engine, question_id: int) -> ResearchQuestionDetail:
    """Build ResearchQuestionDetail including all topic and concept links."""
    from sqlalchemy import select as _select
    from neurodb.schema import (
        Concept,
        QuestionConcept,
        QuestionTopic,
        ResearchQuestion as ResearchQuestionORM,
        Topic,
    )
    from neurodb.api.schemas.research import QuestionConceptLink, QuestionTopicLink
    with get_session(engine) as session:
        q = session.get(ResearchQuestionORM, question_id)
        if q is None:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        topic_rows = session.execute(
            _select(QuestionTopic, Topic)
            .join(Topic, Topic.id == QuestionTopic.topic_id)
            .where(QuestionTopic.question_id == question_id)
        ).all()
        concept_rows = session.execute(
            _select(QuestionConcept, Concept)
            .join(Concept, Concept.id == QuestionConcept.concept_id)
            .where(QuestionConcept.question_id == question_id)
        ).all()
        return ResearchQuestionDetail(
            id=q.id,
            question=q.question,
            status=q.status,
            topic_context=q.topic_context,
            origin_session_id=getattr(q, "origin_session_id", None),
            created_at=q.created_at,
            topics=[
                QuestionTopicLink(topic_id=qt.topic_id, topic_name=t.name, status=qt.status)
                for qt, t in topic_rows
            ],
            concepts=[
                QuestionConceptLink(concept_id=qc.concept_id, concept_name=c.name, status=qc.status)
                for qc, c in concept_rows
            ],
        )
```

Then add these routes (add after the existing `@router.get("/questions")` route):

```python
@router.post("/questions", response_model=ResearchQuestionDetail)
def create_question(
    body: CreateQuestionRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.research_tools import create_research_question
    result = create_research_question(
        engine,
        question=body.question,
        topic_context=body.topic_context,
        origin_session_id=body.origin_session_id,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    question_id = result["id"]

    def _extract():
        from neurodb.db import get_session as _gs
        from neurodb.db.topic_store import extract_question_topics
        with _gs(engine) as session:
            extract_question_topics(session, question_id, body.question)

    threading.Thread(target=_extract, daemon=True).start()
    return _question_detail(engine, question_id)


@router.put("/questions/{question_id}", response_model=ResearchQuestionDetail)
def update_question(
    question_id: int,
    body: UpdateQuestionRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.research_tools import update_research_question
    result = update_research_question(
        engine,
        question_id,
        question=body.question,
        topic_context=body.topic_context,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return _question_detail(engine, question_id)


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(
    question_id: int,
    engine: Engine = Depends(get_engine),
) -> None:
    from neurodb.research_tools import delete_research_question
    result = delete_research_question(engine, question_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])


@router.get("/questions/{question_id}", response_model=ResearchQuestionDetail)
def get_question(
    question_id: int,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    return _question_detail(engine, question_id)


@router.post("/questions/{question_id}/topics", response_model=ResearchQuestionDetail)
def add_question_topic(
    question_id: int,
    body: AddTopicLinkRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.schema import ResearchQuestion as ResearchQuestionORM
    from neurodb.db.topic_store import link_question_topic
    with get_session(engine) as session:
        if session.get(ResearchQuestionORM, question_id) is None:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        link_question_topic(session, question_id, body.topic_id, status="confirmed")
    return _question_detail(engine, question_id)


@router.patch("/questions/{question_id}/topics/{topic_id}", response_model=ResearchQuestionDetail)
def patch_question_topic(
    question_id: int,
    topic_id: int,
    body: PatchLinkStatusRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.db.topic_store import update_question_topic_status
    with get_session(engine) as session:
        found = update_question_topic_status(session, question_id, topic_id, body.status)
    if not found:
        raise HTTPException(status_code=404, detail=f"Topic link {question_id}/{topic_id} not found")
    return _question_detail(engine, question_id)


@router.delete("/questions/{question_id}/topics/{topic_id}", status_code=204)
def remove_question_topic(
    question_id: int,
    topic_id: int,
    engine: Engine = Depends(get_engine),
) -> None:
    from neurodb.db.topic_store import unlink_question_topic
    with get_session(engine) as session:
        found = unlink_question_topic(session, question_id, topic_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Topic link {question_id}/{topic_id} not found")


@router.post("/questions/{question_id}/concepts", response_model=ResearchQuestionDetail)
def add_question_concept(
    question_id: int,
    body: AddConceptLinkRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.schema import ResearchQuestion as ResearchQuestionORM
    from neurodb.db.topic_store import link_question_concept
    with get_session(engine) as session:
        if session.get(ResearchQuestionORM, question_id) is None:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        link_question_concept(session, question_id, body.concept_id, status="confirmed")
    return _question_detail(engine, question_id)


@router.patch("/questions/{question_id}/concepts/{concept_id}", response_model=ResearchQuestionDetail)
def patch_question_concept(
    question_id: int,
    concept_id: int,
    body: PatchLinkStatusRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.db.topic_store import update_question_concept_status
    with get_session(engine) as session:
        found = update_question_concept_status(session, question_id, concept_id, body.status)
    if not found:
        raise HTTPException(status_code=404, detail=f"Concept link {question_id}/{concept_id} not found")
    return _question_detail(engine, question_id)


@router.delete("/questions/{question_id}/concepts/{concept_id}", status_code=204)
def remove_question_concept(
    question_id: int,
    concept_id: int,
    engine: Engine = Depends(get_engine),
) -> None:
    from neurodb.db.topic_store import unlink_question_concept
    with get_session(engine) as session:
        found = unlink_question_concept(session, question_id, concept_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Concept link {question_id}/{concept_id} not found")
```

Also update the existing `get_questions` route to support `topic_id` filtering:

```python
@router.get("/questions")
def get_questions(
    engine: Engine = Depends(get_engine),
    status: list[str] | None = Query(default=None),
    topic_id: int | None = Query(default=None),
) -> list[ResearchQuestionDetail]:
    from sqlalchemy import select as _select
    from neurodb.schema import QuestionTopic, ResearchQuestion as ResearchQuestionORM
    with get_session(engine) as session:
        query = _select(ResearchQuestionORM)
        if status:
            query = query.where(ResearchQuestionORM.status.in_(status))
        if topic_id is not None:
            query = query.where(
                ResearchQuestionORM.id.in_(
                    _select(QuestionTopic.question_id).where(
                        QuestionTopic.topic_id == topic_id,
                        QuestionTopic.status == "confirmed",
                    )
                )
            )
        rows = session.execute(query.order_by(ResearchQuestionORM.created_at.desc())).scalars().all()
        return [_question_detail(engine, r.id) for r in rows]
```

- [ ] **Step 5: Run all new tests**

```bash
uv run pytest tests/unit/test_api_research_phase1.py tests/integration/test_question_phase1.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: same pass/fail count as before.

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/api/schemas/research.py src/neurodb/api/routes/research.py \
        tests/unit/test_api_research_phase1.py tests/integration/test_question_phase1.py
git commit -m "feat: add Phase 1 question CRUD, topic/concept link routes, and topic_id filter"
```

---

## Task 7: Agent Tool — extract_question_topics

**Files:**
- Modify: `src/neurodb/agents/research_agent.py`

- [ ] **Step 1: Add tool definition to the tools list**

In `src/neurodb/agents/research_agent.py`, find `_RESEARCH_TOOLS` (the list of tool dicts). Add this entry after the `record_research_question` tool:

```python
    {
        "name": "extract_question_topics",
        "description": "Match a research question against existing topics and concepts; persist pending suggestions the user can confirm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question_id": {"type": "integer"},
                "question_text": {"type": "string"},
            },
            "required": ["question_id", "question_text"],
        },
    },
```

- [ ] **Step 2: Add handler in _execute_tool_block**

In the `_execute_tool_block` method, find the `if block.tool_name == "record_research_question":` branch. After the `return json.dumps(record_research_question(...))` line, the handler now also calls extraction. Replace the entire branch:

```python
        if block.tool_name == "record_research_question":
            result = record_research_question(
                self._engine,
                block.tool_input["question"],
                block.tool_input["topic_context"],
                status=block.tool_input.get("status", "open"),
            )
            if "id" in result:
                from neurodb.db import get_session as _gs
                from neurodb.db.topic_store import extract_question_topics
                with _gs(self._engine) as session:
                    suggestions = extract_question_topics(
                        session,
                        result["id"],
                        block.tool_input["question"],
                    )
                result["suggestions"] = suggestions
            return json.dumps(result)
        if block.tool_name == "extract_question_topics":
            from neurodb.db import get_session as _gs
            from neurodb.db.topic_store import extract_question_topics
            with _gs(self._engine) as session:
                return json.dumps(extract_question_topics(
                    session,
                    block.tool_input["question_id"],
                    block.tool_input["question_text"],
                ))
```

- [ ] **Step 3: Run the existing research agent tests**

```bash
uv run pytest tests/unit/test_research_agent.py -v
```

Expected: all tests pass (no regressions).

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: same pass/fail count as before.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/agents/research_agent.py
git commit -m "feat: add extract_question_topics agent tool and inline call from record_research_question"
```

---

## Task 8: Frontend — Types and API Client

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add new types to types.ts**

Append to `frontend/src/api/types.ts`:

```typescript
export interface QuestionTopicLink {
  topic_id: number
  topic_name: string
  status: string  // 'pending' | 'confirmed'
}

export interface QuestionConceptLink {
  concept_id: number
  concept_name: string
  status: string
}

export interface ResearchQuestionDetail {
  id: number
  question: string
  status: string
  topic_context: string | null
  origin_session_id: number | null
  created_at: string | null
  topics: QuestionTopicLink[]
  concepts: QuestionConceptLink[]
}

export interface CreateQuestionRequest {
  question: string
  topic_context?: string
  origin_session_id?: number
}
```

- [ ] **Step 2: Add new API methods to client.ts**

In `frontend/src/api/client.ts`, add the import for the new types at the top:

```typescript
import type {
  ...existing imports...
  CreateQuestionRequest,
  QuestionConceptLink,
  QuestionTopicLink,
  ResearchQuestionDetail,
} from './types'
```

Then add these methods to the `api` object:

```typescript
  getResearchQuestionsDetail: (statuses: string[] = [], topicId?: number) => {
    const params = new URLSearchParams()
    statuses.forEach(status => params.append('status', status))
    if (topicId !== undefined) params.set('topic_id', String(topicId))
    const query = params.toString()
    return get<ResearchQuestionDetail[]>(query ? `/api/research/questions?${query}` : '/api/research/questions')
  },
  getQuestionDetail: (id: number) =>
    get<ResearchQuestionDetail>(`/api/research/questions/${id}`),
  createQuestion: (body: CreateQuestionRequest) =>
    post<ResearchQuestionDetail>('/api/research/questions', body),
  updateQuestion: (id: number, body: { question?: string; topic_context?: string }) =>
    put<ResearchQuestionDetail>(`/api/research/questions/${id}`, body),
  deleteQuestion: (id: number) =>
    del<void>(`/api/research/questions/${id}`),
  addQuestionTopic: (questionId: number, topicId: number) =>
    post<ResearchQuestionDetail>(`/api/research/questions/${questionId}/topics`, { topic_id: topicId }),
  confirmQuestionTopic: (questionId: number, topicId: number) =>
    patch<ResearchQuestionDetail>(`/api/research/questions/${questionId}/topics/${topicId}`, { status: 'confirmed' }),
  removeQuestionTopic: (questionId: number, topicId: number) =>
    del<void>(`/api/research/questions/${questionId}/topics/${topicId}`),
  addQuestionConcept: (questionId: number, conceptId: number) =>
    post<ResearchQuestionDetail>(`/api/research/questions/${questionId}/concepts`, { concept_id: conceptId }),
  confirmQuestionConcept: (questionId: number, conceptId: number) =>
    patch<ResearchQuestionDetail>(`/api/research/questions/${questionId}/concepts/${conceptId}`, { status: 'confirmed' }),
  removeQuestionConcept: (questionId: number, conceptId: number) =>
    del<void>(`/api/research/questions/${questionId}/concepts/${conceptId}`),
```

- [ ] **Step 3: Type-check the frontend**

```bash
cd /home/oldha/projects/neuroDb/frontend && npx tsc --noEmit
```

Expected: no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "feat: add ResearchQuestionDetail types and question CRUD/link API client methods"
```

---

## Task 9: ResearchPanel UI

**Files:**
- Modify: `frontend/src/pages/ResearchPanel.tsx`

- [ ] **Step 1: Add question creation form and extend question list**

Replace the question section of `ResearchPanel.tsx`. The existing file already has a `Section` collapsible component and `StatusFilters` — reuse both.

Find the `QuestionStatusChip` function (around line 157) and the place in the main panel where questions are rendered. The changes needed are:

**A. Import new types and client methods** — add to the existing imports at the top:

```typescript
import type { ResearchQuestionDetail, QuestionTopicLink, QuestionConceptLink } from '../api/types'
```

**B. Add `QuestionCreateForm` component** — add this before the main panel component:

```typescript
function QuestionCreateForm({ onCreated }: { onCreated: () => void }) {
  const [question, setQuestion] = useState('')
  const [topicContext, setTopicContext] = useState('')
  const create = useMutation({
    mutationFn: () => api.createQuestion({ question, topic_context: topicContext || undefined }),
    onSuccess: () => {
      setQuestion('')
      setTopicContext('')
      onCreated()
    },
  })
  return (
    <form
      onSubmit={e => { e.preventDefault(); if (question.trim()) create.mutate() }}
      style={{ marginBottom: 12 }}
    >
      <textarea
        value={question}
        onChange={e => setQuestion(e.target.value)}
        placeholder="Enter a research question…"
        rows={3}
        style={{ width: '100%', fontSize: 12, padding: 6, boxSizing: 'border-box', resize: 'vertical' }}
      />
      <input
        value={topicContext}
        onChange={e => setTopicContext(e.target.value)}
        placeholder="Topic context (optional)"
        style={{ width: '100%', fontSize: 12, padding: 4, marginTop: 4, boxSizing: 'border-box' }}
      />
      <button
        type="submit"
        disabled={!question.trim() || create.isPending}
        style={{ marginTop: 6, fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
      >
        {create.isPending ? 'Saving…' : 'Save Question'}
      </button>
      {create.isError && (
        <div style={{ color: '#dc2626', fontSize: 11, marginTop: 4 }}>
          {String(create.error)}
        </div>
      )}
    </form>
  )
}
```

**C. Add `QuestionRow` component** — handles badges, pending chips, and delete:

```typescript
function QuestionRow({ question, onMutated }: { question: ResearchQuestionDetail; onMutated: () => void }) {
  const queryClient = useQueryClient()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['research-questions-detail'] })

  const archive = useMutation({
    mutationFn: () => api.archiveQuestion(question.id),
    onSuccess: () => { invalidate(); onMutated() },
  })
  const del = useMutation({
    mutationFn: () => api.deleteQuestion(question.id),
    onSuccess: () => { invalidate(); onMutated() },
  })
  const confirmTopic = useMutation({
    mutationFn: (topicId: number) => api.confirmQuestionTopic(question.id, topicId),
    onSuccess: invalidate,
  })
  const dismissTopic = useMutation({
    mutationFn: (topicId: number) => api.removeQuestionTopic(question.id, topicId),
    onSuccess: invalidate,
  })
  const confirmConcept = useMutation({
    mutationFn: (conceptId: number) => api.confirmQuestionConcept(question.id, conceptId),
    onSuccess: invalidate,
  })
  const dismissConcept = useMutation({
    mutationFn: (conceptId: number) => api.removeQuestionConcept(question.id, conceptId),
    onSuccess: invalidate,
  })

  const confirmedTopics = question.topics.filter(t => t.status === 'confirmed')
  const pendingTopics = question.topics.filter(t => t.status === 'pending')
  const confirmedConcepts = question.concepts.filter(c => c.status === 'confirmed')
  const pendingConcepts = question.concepts.filter(c => c.status === 'pending')

  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: '8px 10px', marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ fontSize: 12, color: '#1e293b', flex: 1 }}>{question.question}</div>
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          <QuestionStatusChip question={question} />
          <button
            type="button"
            onClick={() => {
              if (window.confirm('Delete this question and all its topic/concept links?')) {
                del.mutate()
              }
            }}
            disabled={del.isPending}
            style={{ fontSize: 11, padding: '2px 7px', border: '1px solid #fca5a5', borderRadius: 4, background: '#fff', color: '#dc2626', cursor: 'pointer' }}
          >
            {del.isPending ? '…' : 'Delete'}
          </button>
        </div>
      </div>

      {/* Confirmed topic badges */}
      {confirmedTopics.length > 0 && (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 6 }}>
          {confirmedTopics.map(t => (
            <span key={t.topic_id} style={{ fontSize: 10, padding: '1px 6px', background: '#dbeafe', color: '#1e40af', borderRadius: 10 }}>
              {t.topic_name}
            </span>
          ))}
          {confirmedConcepts.map(c => (
            <span key={c.concept_id} style={{ fontSize: 10, padding: '1px 6px', background: '#dcfce7', color: '#166534', borderRadius: 10 }}>
              {c.concept_name}
            </span>
          ))}
        </div>
      )}

      {/* Pending suggestion chips */}
      {(pendingTopics.length > 0 || pendingConcepts.length > 0) && (
        <div style={{ marginTop: 6 }}>
          <div style={{ fontSize: 10, color: '#64748b', marginBottom: 3 }}>Suggested tags — confirm or dismiss:</div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {pendingTopics.map(t => (
              <span key={t.topic_id} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, padding: '1px 4px', border: '1px dashed #93c5fd', borderRadius: 10, color: '#1e40af' }}>
                {t.topic_name}
                <button type="button" onClick={() => confirmTopic.mutate(t.topic_id)} style={{ fontSize: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: '#16a34a', padding: 0 }}>✓</button>
                <button type="button" onClick={() => dismissTopic.mutate(t.topic_id)} style={{ fontSize: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: '#dc2626', padding: 0 }}>✕</button>
              </span>
            ))}
            {pendingConcepts.map(c => (
              <span key={c.concept_id} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, padding: '1px 4px', border: '1px dashed #86efac', borderRadius: 10, color: '#166534' }}>
                {c.concept_name}
                <button type="button" onClick={() => confirmConcept.mutate(c.concept_id)} style={{ fontSize: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: '#16a34a', padding: 0 }}>✓</button>
                <button type="button" onClick={() => dismissConcept.mutate(c.concept_id)} style={{ fontSize: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: '#dc2626', padding: 0 }}>✕</button>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

**D. Update the questions section in the main panel component**

Find where `getResearchQuestions` is used (around the questions list rendering in the main component). Replace it with `getResearchQuestionsDetail` and wrap the list in the `Section` collapsible + add a topic filter.

The question list query should be:

```typescript
const [selectedTopicId, setSelectedTopicId] = useState<number | undefined>(undefined)
const [selectedStatuses, setSelectedStatuses] = useState<string[]>([])

const { data: questions = [], refetch: refetchQuestions } = useQuery({
  queryKey: ['research-questions-detail', selectedStatuses, selectedTopicId],
  queryFn: () => api.getResearchQuestionsDetail(selectedStatuses, selectedTopicId),
})
```

The topic filter needs a list of all topics. Add this query (only needs topic names and IDs):

```typescript
const { data: allTopics = [] } = useQuery({
  queryKey: ['topics-for-filter'],
  queryFn: () => api.executeSQL('SELECT id, name FROM topics WHERE status = \'active\' ORDER BY name'),
})
const topicOptions = (allTopics as { columns: string[]; rows: unknown[][] })
  ?.rows?.map((r: unknown[]) => ({ id: r[0] as number, name: r[1] as string })) ?? []
```

The question list section should be wrapped as:

```tsx
<Section title="Research Questions" count={questions.length}>
  <QuestionCreateForm onCreated={() => refetchQuestions()} />

  {/* Topic filter */}
  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
    <button
      type="button"
      onClick={() => setSelectedTopicId(undefined)}
      style={{
        fontSize: 11, padding: '2px 7px', border: '1px solid #cbd5e1', borderRadius: 4,
        background: selectedTopicId === undefined ? '#1e3a8a' : '#fff',
        color: selectedTopicId === undefined ? '#fff' : '#334155',
        cursor: 'pointer',
      }}
    >
      All topics
    </button>
    {topicOptions.map((t: { id: number; name: string }) => (
      <button
        key={t.id}
        type="button"
        onClick={() => setSelectedTopicId(selectedTopicId === t.id ? undefined : t.id)}
        style={{
          fontSize: 11, padding: '2px 7px', border: '1px solid #cbd5e1', borderRadius: 4,
          background: selectedTopicId === t.id ? '#1e3a8a' : '#fff',
          color: selectedTopicId === t.id ? '#fff' : '#334155',
          cursor: 'pointer',
        }}
      >
        {t.name}
      </button>
    ))}
  </div>

  {questions.map(q => (
    <QuestionRow key={q.id} question={q} onMutated={() => refetchQuestions()} />
  ))}
</Section>
```

- [ ] **Step 2: Type-check the frontend**

```bash
cd /home/oldha/projects/neuroDb/frontend && npx tsc --noEmit
```

Expected: no type errors.

- [ ] **Step 3: Run frontend tests**

```bash
cd /home/oldha/projects/neuroDb/frontend && npm test -- --watchAll=false
```

Expected: existing tests pass; no new failures.

- [ ] **Step 4: Run full backend test suite**

```bash
uv run pytest tests/ -q
```

Expected: same pass/fail count as before.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ResearchPanel.tsx
git commit -m "feat: add question creation form, collapsible list, pending chips, and delete to ResearchPanel"
```

---

## Task 10: Final Verification and projectStatus Update

**Files:**
- Modify: `docs/projectStatus.md`
- Modify: `docs/researchQuestionDesignClaude.md`

- [ ] **Step 1: Run full test suite one final time**

```bash
uv run pytest tests/ -q
```

Expected: no new failures.

- [ ] **Step 2: Update projectStatus.md**

In `docs/projectStatus.md`:
- Add a new Research epoch row (or update the existing one) noting Phase 1 implementation is in progress.
- Add the implementation plan to the Active Plans table:
  ```
  | `docs/superpowers/plans/2026-06-01-research-question-phase1.md` | Research Question Phase 1 implementation plan |
  ```

- [ ] **Step 3: Note implementation start in researchQuestionDesignClaude.md**

At the top of `docs/researchQuestionDesignClaude.md`, update the note at the bottom of Phase 1 section or add a line:
```
_Phase 1 implementation started 2026-06-01._
```

- [ ] **Step 4: Commit**

```bash
git add docs/projectStatus.md docs/researchQuestionDesignClaude.md
git commit -m "docs: note Phase 1 implementation start; add plan to projectStatus"
```
