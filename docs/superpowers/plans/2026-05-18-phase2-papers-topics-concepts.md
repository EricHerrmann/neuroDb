# Phase 2 — Papers, Topics, Concepts, and Study Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class `papers`, `topics`, and `concepts` tables; generalize `StudyNote` to anchor to topics/concepts/papers; add a `topic_store` helper; extend the Tutor agent with topic retrieval tools.

**Architecture:** Rename the existing `KnowledgeSource` ORM class and `knowledge_sources` DB table to `Paper`/`papers`, add `Topic` and `Concept` ORM models with five linking tables, make `StudyNote` anchors polymorphic via nullable FKs, and add a `topic_store` module in `src/neurodb/db/` with SQL-based retrieval helpers. The Tutor agent gains `search_topics` and `get_topic_bundle` tools plus an extended `queue_source` that accepts topic names.

**Tech Stack:** Python 3.12, SQLAlchemy ORM, DuckDB (runtime), SQLite (unit tests), pytest, FastAPI, React/TypeScript (frontend rename only).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/neurodb/schema.py` | Modify | Rename KnowledgeSource→Paper; add Topic, Concept, five linking ORM models; generalize StudyNote |
| `src/neurodb/db/topic_store.py` | Create | All topic/concept write and retrieval operations |
| `src/neurodb/agents/tutor_agent.py` | Modify | New tools (search_topics, get_topic_bundle), extended queue_source |
| `src/neurodb/api/routes/knowledge_library.py` | Modify | Import rename only |
| `src/neurodb/api/schemas/knowledge_library.py` | Modify | KnowledgeSourceItem → PaperItem |
| `src/neurodb/knowledge_store.py` | Modify | Import rename only (if KnowledgeSource imported) |
| `frontend/src/api/types.ts` | Modify | KnowledgeSourceItem interface rename |
| `frontend/src/api/client.ts` | Modify | Update type import |
| `scripts/migrate_phase2_papers_topics.py` | Create | Idempotent DuckDB migration script |
| `tests/unit/test_topic_concepts_schema.py` | Create | Topic, Concept, linking table schema tests |
| `tests/unit/test_schema_papers.py` | Create | Paper rename and new column tests |
| `tests/unit/test_study_note_anchors.py` | Create | StudyNote nullable anchors tests |
| `tests/unit/test_topic_store.py` | Create | topic_store unit tests |
| `tests/unit/test_migrate_phase2.py` | Create | Migration script tests (DuckDB in-memory) |
| `tests/unit/test_api_knowledge_library.py` | Modify | Update KnowledgeSource → Paper references |
| `tests/unit/test_knowledge_schema.py` | Modify | Update KnowledgeSource → Paper references |
| `tests/unit/test_tutor_agent.py` | Modify | Update import; add tests for new tools |
| `tests/unit/test_research_tools.py` | Modify | Update KnowledgeSource import |
| `tests/unit/test_knowledge_library_page.py` | Modify | Update KnowledgeSource → Paper references |
| `tests/integration/test_phase2_topic_bundle.py` | Create | End-to-end bundle retrieval test |

---

## Task 1: Topic and Concept ORM models

**Files:**
- Modify: `src/neurodb/schema.py`
- Create: `tests/unit/test_topic_concepts_schema.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_topic_concepts_schema.py`:

```python
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Concept, Topic


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


def test_topic_table_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("topics")}
    assert {"id", "name", "description", "status", "created_at", "updated_at"}.issubset(cols)


def test_concept_table_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("concepts")}
    assert {"id", "name", "description", "status", "created_at", "updated_at"}.issubset(cols)


def test_topic_name_is_unique(engine):
    now = _now()
    with Session(engine) as s:
        s.add(Topic(name="stroke recovery", status="active", created_at=now, updated_at=now))
        s.commit()
    with pytest.raises(IntegrityError):
        with Session(engine) as s:
            s.add(Topic(name="stroke recovery", status="active", created_at=now, updated_at=now))
            s.commit()


def test_concept_name_is_unique(engine):
    now = _now()
    with Session(engine) as s:
        s.add(Concept(name="neuroplasticity", status="active", created_at=now, updated_at=now))
        s.commit()
    with pytest.raises(IntegrityError):
        with Session(engine) as s:
            s.add(Concept(name="neuroplasticity", status="active", created_at=now, updated_at=now))
            s.commit()


def test_topic_description_is_optional(engine):
    now = _now()
    with Session(engine) as s:
        s.add(Topic(name="cortical remapping", status="active", created_at=now, updated_at=now))
        s.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_topic_concepts_schema.py -v
```

Expected: `ImportError` — `Topic` and `Concept` not defined in `neurodb.schema`.

- [ ] **Step 3: Add Topic and Concept to schema.py**

Open `src/neurodb/schema.py`. After the `AppPreference` class at the end, add:

```python
class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, Sequence("topics_id_seq"), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(Integer, Sequence("concepts_id_seq"), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_topic_concepts_schema.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_topic_concepts_schema.py
git commit -m "feat: add Topic and Concept ORM models to schema"
```

---

## Task 2: Rename KnowledgeSource → Paper and add new columns

**Files:**
- Modify: `src/neurodb/schema.py`
- Modify: `src/neurodb/agents/tutor_agent.py`
- Modify: `src/neurodb/api/routes/knowledge_library.py`
- Modify: `src/neurodb/api/schemas/knowledge_library.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `tests/unit/test_api_knowledge_library.py`
- Modify: `tests/unit/test_knowledge_schema.py`
- Modify: `tests/unit/test_tutor_agent.py`
- Modify: `tests/unit/test_research_tools.py`
- Modify: `tests/unit/test_knowledge_library_page.py`
- Create: `tests/unit/test_schema_papers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_schema_papers.py`:

```python
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Paper


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


def test_paper_table_exists(engine):
    assert "papers" in inspect(engine).get_table_names()


def test_knowledge_sources_table_does_not_exist_in_new_schema(engine):
    assert "knowledge_sources" not in inspect(engine).get_table_names()


def test_paper_has_original_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("papers")}
    assert {
        "id", "title", "normalized_title", "doi", "url", "source_type",
        "topic_context", "status", "queued_at", "reviewed_at", "summary", "chroma_id",
    }.issubset(cols)


def test_paper_has_new_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("papers")}
    assert {"abstract", "authors_json", "year"}.issubset(cols)


def test_paper_class_importable():
    from neurodb.schema import Paper
    assert Paper.__tablename__ == "papers"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_schema_papers.py -v
```

Expected: `ImportError` — `Paper` not in `neurodb.schema`.

- [ ] **Step 3: Rename KnowledgeSource → Paper in schema.py**

In `src/neurodb/schema.py`:

1. Find the `KnowledgeSource` class and rename it to `Paper`. Change `__tablename__` from `"knowledge_sources"` to `"papers"`. Change the sequence name from `"knowledge_sources_id_seq"` to `"papers_id_seq"`. Update `UniqueConstraint` names from `uq_knowledge_sources_doi` → `uq_papers_doi` and `uq_knowledge_sources_normalized_title` → `uq_papers_normalized_title`. Add three new columns after `chroma_id`:

```python
class Paper(Base):
    """Candidate and approved learning sources surfaced by NeuroTutorAgent."""
    __tablename__ = "papers"
    __table_args__ = (
        UniqueConstraint("doi", name="uq_papers_doi"),
        UniqueConstraint("normalized_title", name="uq_papers_normalized_title"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("papers_id_seq"), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    topic_context: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    queued_at: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    chroma_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 4: Update all source imports**

**`src/neurodb/agents/tutor_agent.py`** — change line `from neurodb.schema import KnowledgeSource` to `from neurodb.schema import Paper`. Change all `KnowledgeSource(` to `Paper(` and `session.query(KnowledgeSource)` to `session.query(Paper)` inside `_execute_queue_source`.

**`src/neurodb/api/routes/knowledge_library.py`** — change `from neurodb.schema import KnowledgeSource` to `from neurodb.schema import Paper`. Replace all `KnowledgeSource` with `Paper` throughout the file.

**`src/neurodb/api/schemas/knowledge_library.py`** — rename class `KnowledgeSourceItem` to `PaperItem`:

```python
class PaperItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    doi: str | None = None
    url: str | None = None
    source_type: str
    topic_context: str
    status: str
    queued_at: str
    reviewed_at: str | None = None
    summary: str | None = None
    warnings: list[str] = []
```

**`src/neurodb/api/routes/knowledge_library.py`** — update the import of `KnowledgeSourceItem` to `PaperItem` and all usages.

**`frontend/src/api/types.ts`** — rename the interface:

```typescript
export interface PaperItem {
  id: number;
  title: string;
  doi?: string;
  url?: string;
  source_type: string;
  topic_context: string;
  status: string;
  queued_at: string;
  reviewed_at?: string;
  summary?: string;
  warnings: string[];
}
```

**`frontend/src/api/client.ts`** — change `import { ..., KnowledgeSourceItem, ... }` to use `PaperItem`. Update all `KnowledgeSourceItem` type references to `PaperItem`.

- [ ] **Step 5: Update test files**

**`tests/unit/test_api_knowledge_library.py`**:
- Line 11: `from neurodb.schema import Base, KnowledgeSource` → `from neurodb.schema import Base, Paper`
- Line 35: `session.add(KnowledgeSource(` → `session.add(Paper(`

**`tests/unit/test_knowledge_schema.py`**:
- `from neurodb.schema import Base, ChatSession, KnowledgeSource, LiteratureSearch` → replace `KnowledgeSource` with `Paper`
- All `KnowledgeSource(` → `Paper(`
- All `KnowledgeSource)` → `Paper)`

**`tests/unit/test_tutor_agent.py`**:
- `from neurodb.schema import Base, KnowledgeSource` → `from neurodb.schema import Base, Paper`
- `session.query(KnowledgeSource)` → `session.query(Paper)`

**`tests/unit/test_research_tools.py`**:
- `KnowledgeSource,` → `Paper,` in the import
- `session.add(KnowledgeSource(` → `session.add(Paper(`

**`tests/unit/test_knowledge_library_page.py`**:
- `from neurodb.schema import Base, KnowledgeSource, ModelCallLog` → replace `KnowledgeSource` with `Paper`
- All `KnowledgeSource(` → `Paper(`
- `session.query(KnowledgeSource)` → `session.query(Paper)`
- Line 39: `assert "KnowledgeSource" in _source()` → `assert "Paper" in _source()`

- [ ] **Step 6: Run full test suite to verify no regressions**

```bash
uv run pytest tests/ -q
```

Expected: same pass/fail count as before this task (the 9 pre-existing failures from `neurodb_models.toml` routing remain; no new failures).

- [ ] **Step 7: Run new schema test**

```bash
uv run pytest tests/unit/test_schema_papers.py -v
```

Expected: all 5 PASS.

- [ ] **Step 8: Commit**

```bash
git add src/neurodb/schema.py \
        src/neurodb/agents/tutor_agent.py \
        src/neurodb/api/routes/knowledge_library.py \
        src/neurodb/api/schemas/knowledge_library.py \
        frontend/src/api/types.ts \
        frontend/src/api/client.ts \
        tests/unit/test_api_knowledge_library.py \
        tests/unit/test_knowledge_schema.py \
        tests/unit/test_tutor_agent.py \
        tests/unit/test_research_tools.py \
        tests/unit/test_knowledge_library_page.py \
        tests/unit/test_schema_papers.py
git commit -m "refactor: rename KnowledgeSource → Paper; add abstract/authors_json/year columns"
```

---

## Task 3: Five linking ORM models

**Files:**
- Modify: `src/neurodb/schema.py`
- Modify: `tests/unit/test_topic_concepts_schema.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_topic_concepts_schema.py` (after existing imports, add `Paper` and linking models; add these test functions at the bottom):

```python
from neurodb.schema import (
    Base, Concept, Topic,
    DatasetPacketPaper, DatasetPacketTopic,
    PaperConcept, PaperTopic, TopicConcept,
)


def test_linking_tables_all_exist(engine):
    names = set(inspect(engine).get_table_names())
    for t in (
        "paper_topics",
        "paper_concepts",
        "topic_concepts",
        "dataset_packet_topics",
        "dataset_packet_papers",
    ):
        assert t in names, f"Table '{t}' missing"


def test_paper_topics_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("paper_topics")}
    assert {"paper_id", "topic_id"}.issubset(cols)


def test_topic_concepts_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("topic_concepts")}
    assert {"topic_id", "concept_id"}.issubset(cols)


def test_paper_topic_unique_constraint_enforced(engine):
    from neurodb.schema import Paper
    now = _now()
    with Session(engine) as s:
        paper = Paper(
            title="Test Paper", normalized_title="test paper",
            source_type="paper", topic_context="test",
            status="pending", queued_at=now,
        )
        topic = Topic(name="test topic", status="active", created_at=now, updated_at=now)
        s.add_all([paper, topic])
        s.flush()
        s.add(PaperTopic(paper_id=paper.id, topic_id=topic.id))
        s.commit()
    with pytest.raises(IntegrityError):
        with Session(engine) as s:
            paper = s.query(Paper).first()
            topic = s.query(Topic).first()
            s.add(PaperTopic(paper_id=paper.id, topic_id=topic.id))
            s.commit()
```

Also update the import block at the top of `test_topic_concepts_schema.py` to include `Paper, PaperTopic, PaperConcept, TopicConcept, DatasetPacketTopic, DatasetPacketPaper`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_topic_concepts_schema.py -v -k "linking"
```

Expected: `ImportError` — linking models not yet defined.

- [ ] **Step 3: Add five linking ORM models to schema.py**

In `src/neurodb/schema.py`, after the `Concept` class, add:

```python
class PaperTopic(Base):
    __tablename__ = "paper_topics"
    __table_args__ = (UniqueConstraint("paper_id", "topic_id", name="uq_paper_topics"),)

    id: Mapped[int] = mapped_column(Integer, Sequence("paper_topics_id_seq"), primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)


class PaperConcept(Base):
    __tablename__ = "paper_concepts"
    __table_args__ = (UniqueConstraint("paper_id", "concept_id", name="uq_paper_concepts"),)

    id: Mapped[int] = mapped_column(Integer, Sequence("paper_concepts_id_seq"), primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), nullable=False, index=True)


class TopicConcept(Base):
    __tablename__ = "topic_concepts"
    __table_args__ = (UniqueConstraint("topic_id", "concept_id", name="uq_topic_concepts"),)

    id: Mapped[int] = mapped_column(Integer, Sequence("topic_concepts_id_seq"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), nullable=False, index=True)


class DatasetPacketTopic(Base):
    __tablename__ = "dataset_packet_topics"
    __table_args__ = (UniqueConstraint("packet_id", "topic_id", name="uq_dataset_packet_topics"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("dataset_packet_topics_id_seq"), primary_key=True
    )
    packet_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_research_packets.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)


class DatasetPacketPaper(Base):
    __tablename__ = "dataset_packet_papers"
    __table_args__ = (UniqueConstraint("packet_id", "paper_id", name="uq_dataset_packet_papers"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("dataset_packet_papers_id_seq"), primary_key=True
    )
    packet_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_research_packets.id"), nullable=False, index=True
    )
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_topic_concepts_schema.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_topic_concepts_schema.py
git commit -m "feat: add PaperTopic, PaperConcept, TopicConcept, DatasetPacketTopic, DatasetPacketPaper ORM models"
```

---

## Task 4: Generalize StudyNote

**Files:**
- Modify: `src/neurodb/schema.py`
- Create: `tests/unit/test_study_note_anchors.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_study_note_anchors.py`:

```python
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import (
    Base, Concept, DatasetIndex, IngestRun, Paper, StudyNote, Topic,
)


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


def _make_dataset(session):
    run = IngestRun(source="test", run_at=_now(), version="1")
    session.add(run)
    session.flush()
    idx = DatasetIndex(source="test", source_id="ds1", run_id=run.id)
    session.add(idx)
    session.flush()
    return idx


def test_study_note_accepts_index_id_anchor(engine):
    with Session(engine) as s:
        idx = _make_dataset(s)
        s.add(StudyNote(index_id=idx.id, concept_tag="plasticity", tagged_at=_now()))
        s.commit()


def test_study_note_accepts_topic_id_anchor(engine):
    with Session(engine) as s:
        topic = Topic(name="hippocampal plasticity", status="active",
                      created_at=_now(), updated_at=_now())
        s.add(topic)
        s.flush()
        s.add(StudyNote(topic_id=topic.id, concept_tag="LTP", tagged_at=_now()))
        s.commit()


def test_study_note_accepts_concept_id_anchor(engine):
    with Session(engine) as s:
        concept = Concept(name="synaptic pruning", status="active",
                          created_at=_now(), updated_at=_now())
        s.add(concept)
        s.flush()
        s.add(StudyNote(concept_id=concept.id, concept_tag="pruning", tagged_at=_now()))
        s.commit()


def test_study_note_accepts_paper_id_anchor(engine):
    with Session(engine) as s:
        paper = Paper(title="LTP Review", normalized_title="ltp review",
                      source_type="paper", topic_context="plasticity",
                      status="pending", queued_at=_now())
        s.add(paper)
        s.flush()
        s.add(StudyNote(paper_id=paper.id, concept_tag="LTP", tagged_at=_now()))
        s.commit()


def test_study_note_rejects_all_null_anchors(engine):
    with pytest.raises(Exception):
        with Session(engine) as s:
            s.add(StudyNote(concept_tag="LTP", tagged_at=_now()))
            s.commit()


def test_study_note_index_id_is_nullable(engine):
    cols = {c["name"]: c for c in __import__("sqlalchemy", fromlist=["inspect"]).inspect(engine).get_columns("study_notes")}
    assert cols["index_id"]["nullable"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_study_note_anchors.py -v
```

Expected: FAIL — `topic_id` column does not exist; `index_id` is not nullable.

- [ ] **Step 3: Update StudyNote in schema.py**

Find the `StudyNote` class. Add `CheckConstraint` to the SQLAlchemy imports at the top of the file:

```python
from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, Sequence, String, Text, UniqueConstraint
```

Replace the `StudyNote` class entirely:

```python
class StudyNote(Base):
    __tablename__ = "study_notes"
    __table_args__ = (
        CheckConstraint(
            "index_id IS NOT NULL OR topic_id IS NOT NULL OR "
            "concept_id IS NOT NULL OR paper_id IS NOT NULL",
            name="ck_study_notes_one_anchor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("study_notes_id_seq"), primary_key=True)
    index_id: Mapped[int | None] = mapped_column(
        ForeignKey("datasets_index.id"), nullable=True, index=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id"), nullable=True, index=True
    )
    concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("concepts.id"), nullable=True, index=True
    )
    paper_id: Mapped[int | None] = mapped_column(
        ForeignKey("papers.id"), nullable=True, index=True
    )
    concept_tag: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    section_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagged_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_study_note_anchors.py -v
```

Expected: all 6 PASS.

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
uv run pytest tests/ -q
```

Expected: same pass/fail as baseline (no new failures beyond the 9 pre-existing).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_study_note_anchors.py
git commit -m "feat: generalize StudyNote — nullable index_id, add topic_id/concept_id/paper_id anchors"
```

---

## Task 5: Migration script

**Files:**
- Create: `scripts/migrate_phase2_papers_topics.py`
- Create: `tests/unit/test_migrate_phase2.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_migrate_phase2.py`:

```python
"""Migration tests use DuckDB in-memory — ALTER COLUMN DROP NOT NULL is DuckDB-only syntax."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))


_PRE_MIGRATION_STMTS = [
    "CREATE SEQUENCE IF NOT EXISTS ingest_runs_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS ingest_runs (
        id INTEGER DEFAULT nextval('ingest_runs_id_seq') PRIMARY KEY,
        source VARCHAR(64) NOT NULL,
        run_at VARCHAR(32) NOT NULL,
        version VARCHAR(32) NOT NULL,
        notes TEXT
    )""",
    "CREATE SEQUENCE IF NOT EXISTS datasets_index_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS datasets_index (
        id INTEGER DEFAULT nextval('datasets_index_id_seq') PRIMARY KEY,
        source VARCHAR(64) NOT NULL,
        source_id VARCHAR(128) NOT NULL,
        run_id INTEGER NOT NULL,
        UNIQUE(source, source_id)
    )""",
    "CREATE SEQUENCE IF NOT EXISTS knowledge_sources_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS knowledge_sources (
        id INTEGER DEFAULT nextval('knowledge_sources_id_seq') PRIMARY KEY,
        title TEXT NOT NULL,
        normalized_title VARCHAR(512) NOT NULL,
        doi VARCHAR(256),
        url TEXT,
        source_type VARCHAR(32) NOT NULL,
        topic_context TEXT NOT NULL,
        status VARCHAR(16) NOT NULL,
        queued_at VARCHAR(32) NOT NULL,
        reviewed_at VARCHAR(32),
        summary TEXT,
        chroma_id VARCHAR(128),
        UNIQUE(normalized_title)
    )""",
    "CREATE SEQUENCE IF NOT EXISTS study_notes_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS study_notes (
        id INTEGER DEFAULT nextval('study_notes_id_seq') PRIMARY KEY,
        index_id INTEGER NOT NULL,
        concept_tag VARCHAR(128) NOT NULL,
        section_ref VARCHAR(64),
        note_text TEXT,
        tagged_at VARCHAR(32) NOT NULL
    )""",
    """INSERT INTO knowledge_sources
        (title, normalized_title, source_type, topic_context, status, queued_at)
        VALUES ('LTP Study', 'ltp study', 'paper', 'plasticity', 'pending', '2026-01-01T00:00:00')
    """,
]


@pytest.fixture
def pre_migration_engine():
    engine = create_engine("duckdb:///:memory:")
    with engine.begin() as conn:
        for stmt in _PRE_MIGRATION_STMTS:
            conn.execute(text(stmt))
    yield engine
    engine.dispose()


def test_rename_knowledge_sources_to_papers(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    tables = set(inspect(pre_migration_engine).get_table_names())
    assert "papers" in tables
    assert "knowledge_sources" not in tables


def test_seeded_row_preserved_in_papers(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    with pre_migration_engine.connect() as conn:
        row = conn.execute(
            text("SELECT title FROM papers WHERE title = 'LTP Study'")
        ).fetchone()
    assert row is not None


def test_papers_has_new_columns(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    cols = {c["name"] for c in inspect(pre_migration_engine).get_columns("papers")}
    assert {"abstract", "authors_json", "year"}.issubset(cols)


def test_study_notes_index_id_becomes_nullable(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    col = next(
        c for c in inspect(pre_migration_engine).get_columns("study_notes")
        if c["name"] == "index_id"
    )
    assert col["nullable"] is True


def test_study_notes_has_new_anchor_columns(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    cols = {c["name"] for c in inspect(pre_migration_engine).get_columns("study_notes")}
    assert {"topic_id", "concept_id", "paper_id"}.issubset(cols)


def test_migration_is_idempotent(pre_migration_engine):
    from migrate_phase2_papers_topics import run_migration
    run_migration(pre_migration_engine)
    run_migration(pre_migration_engine)  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_migrate_phase2.py -v
```

Expected: `ModuleNotFoundError` — `migrate_phase2_papers_topics` not found.

- [ ] **Step 3: Write the migration script**

Create `scripts/migrate_phase2_papers_topics.py`:

```python
#!/usr/bin/env python
"""Phase 2 migration: rename knowledge_sources → papers, add topics/concepts tables.

Safe to re-run. Each step checks current state before executing.

Usage:
    uv run scripts/migrate_phase2_papers_topics.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, text

from neurodb.schema import Base


def _table_exists(conn, table: str) -> bool:
    result = conn.execute(
        text("SELECT count(*) FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    )
    return result.scalar() > 0


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() > 0


def _is_nullable(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    row = result.fetchone()
    return row is not None and row[0] == "YES"


def run_migration(engine) -> None:
    with engine.begin() as conn:
        # Step 1: rename knowledge_sources → papers
        if _table_exists(conn, "knowledge_sources") and not _table_exists(conn, "papers"):
            conn.execute(text("ALTER TABLE knowledge_sources RENAME TO papers"))
            print("✓ Renamed knowledge_sources → papers")
        elif _table_exists(conn, "papers"):
            print("✓ papers already exists — skip rename")
        else:
            print("⚠ knowledge_sources not found and papers not found — nothing to rename")

        # Steps 2–4: add new columns to papers
        for col, ddl in [
            ("abstract", "TEXT"),
            ("authors_json", "TEXT"),
            ("year", "INTEGER"),
        ]:
            if _table_exists(conn, "papers") and not _column_exists(conn, "papers", col):
                conn.execute(text(f"ALTER TABLE papers ADD COLUMN {col} {ddl}"))
                print(f"✓ Added papers.{col}")
            else:
                print(f"✓ papers.{col} already present — skip")

    # Step 5: create new tables via create_all (topics, concepts, linking tables)
    Base.metadata.create_all(engine, checkfirst=True)
    print("✓ create_all complete — new tables created if missing")

    with engine.begin() as conn:
        # Step 6: make study_notes.index_id nullable
        if _table_exists(conn, "study_notes") and not _is_nullable(conn, "study_notes", "index_id"):
            conn.execute(text("ALTER TABLE study_notes ALTER COLUMN index_id DROP NOT NULL"))
            print("✓ study_notes.index_id is now nullable")
        else:
            print("✓ study_notes.index_id already nullable — skip")

        # Steps 7–9: add new FK columns to study_notes
        for col, ref in [
            ("topic_id", "topics(id)"),
            ("concept_id", "concepts(id)"),
            ("paper_id", "papers(id)"),
        ]:
            if _table_exists(conn, "study_notes") and not _column_exists(conn, "study_notes", col):
                conn.execute(
                    text(f"ALTER TABLE study_notes ADD COLUMN {col} INTEGER REFERENCES {ref}")
                )
                print(f"✓ Added study_notes.{col}")
            else:
                print(f"✓ study_notes.{col} already present — skip")

        # Step 10: drop old unique constraint (best-effort)
        try:
            conn.execute(
                text("ALTER TABLE study_notes DROP CONSTRAINT uq_study_note_index_concept")
            )
            print("✓ Dropped uq_study_note_index_concept")
        except Exception:
            print("✓ uq_study_note_index_concept already gone — skip")


if __name__ == "__main__":
    db_path = os.environ.get("NEURODB_DB_PATH", "neurodb.db")
    engine = create_engine(f"duckdb:///{db_path}")
    run_migration(engine)
    print("\nMigration complete.")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_migrate_phase2.py -v
```

Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_phase2_papers_topics.py tests/unit/test_migrate_phase2.py
git commit -m "feat: add Phase 2 migration script — rename knowledge_sources to papers, add topics/concepts"
```

---

## Task 6: topic_store helper

**Files:**
- Create: `src/neurodb/db/topic_store.py`
- Create: `tests/unit/test_topic_store.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_topic_store.py`:

```python
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import (
    Base, Concept, DatasetIndex, DatasetResearchPacket,
    IngestRun, Paper, StudyNote, Topic,
)
from neurodb.db.topic_store import (
    get_or_create_concept,
    get_or_create_topic,
    get_topic_bundle,
    link_packet_paper,
    link_packet_topic,
    link_paper_concept,
    link_paper_topic,
    link_topic_concept,
    search_topics,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_paper(session):
    paper = Paper(
        title="LTP Paper", normalized_title="ltp paper",
        source_type="paper", topic_context="plasticity",
        status="approved", queued_at=_now(),
    )
    session.add(paper)
    session.flush()
    return paper


def _make_packet(session):
    run = IngestRun(source="test", run_at=_now(), version="1")
    session.add(run)
    session.flush()
    idx = DatasetIndex(source="test", source_id="ds1", run_id=run.id)
    session.add(idx)
    session.flush()
    packet = DatasetResearchPacket(
        index_id=idx.id, source="test", source_id="ds1",
        usefulness_state="partial",
        supported_workflows_json="[]", unsupported_workflows_json="[]",
        missing_context_json="[]", provenance_json="{}", confidence_json="{}",
        harvested_at=_now(), run_id=run.id,
    )
    session.add(packet)
    session.flush()
    return packet


# --- get_or_create_topic ---

def test_get_or_create_topic_creates_new(session):
    topic = get_or_create_topic(session, "hippocampal plasticity")
    session.commit()
    assert topic.id is not None
    assert topic.name == "hippocampal plasticity"
    assert topic.status == "active"


def test_get_or_create_topic_is_idempotent(session):
    t1 = get_or_create_topic(session, "stroke recovery")
    session.flush()
    t2 = get_or_create_topic(session, "stroke recovery")
    session.flush()
    assert t1.id == t2.id


def test_get_or_create_topic_strips_whitespace(session):
    t1 = get_or_create_topic(session, "  basal ganglia  ")
    session.flush()
    t2 = get_or_create_topic(session, "basal ganglia")
    session.flush()
    assert t1.id == t2.id


# --- get_or_create_concept ---

def test_get_or_create_concept_creates_new(session):
    concept = get_or_create_concept(session, "neuroplasticity")
    session.commit()
    assert concept.id is not None
    assert concept.name == "neuroplasticity"


def test_get_or_create_concept_is_idempotent(session):
    c1 = get_or_create_concept(session, "GABA")
    session.flush()
    c2 = get_or_create_concept(session, "GABA")
    session.flush()
    assert c1.id == c2.id


# --- link functions ---

def test_link_paper_topic_is_idempotent(session):
    paper = _make_paper(session)
    topic = get_or_create_topic(session, "stroke recovery")
    session.flush()
    link_paper_topic(session, paper.id, topic.id)
    link_paper_topic(session, paper.id, topic.id)
    session.commit()


def test_link_paper_concept_is_idempotent(session):
    paper = _make_paper(session)
    concept = get_or_create_concept(session, "neuroplasticity")
    session.flush()
    link_paper_concept(session, paper.id, concept.id)
    link_paper_concept(session, paper.id, concept.id)
    session.commit()


def test_link_topic_concept_is_idempotent(session):
    topic = get_or_create_topic(session, "hippocampal plasticity")
    concept = get_or_create_concept(session, "LTP")
    session.flush()
    link_topic_concept(session, topic.id, concept.id)
    link_topic_concept(session, topic.id, concept.id)
    session.commit()


def test_link_packet_topic_is_idempotent(session):
    packet = _make_packet(session)
    topic = get_or_create_topic(session, "memory consolidation")
    session.flush()
    link_packet_topic(session, packet.id, topic.id)
    link_packet_topic(session, packet.id, topic.id)
    session.commit()


def test_link_packet_paper_is_idempotent(session):
    packet = _make_packet(session)
    paper = _make_paper(session)
    session.flush()
    link_packet_paper(session, packet.id, paper.id)
    link_packet_paper(session, packet.id, paper.id)
    session.commit()


# --- search_topics ---

def test_search_topics_returns_name_match(session):
    get_or_create_topic(session, "hippocampal plasticity", "relates to memory")
    get_or_create_topic(session, "stroke recovery", "motor learning after stroke")
    session.commit()
    results = search_topics(session, "plasticity")
    names = [r["name"] for r in results]
    assert "hippocampal plasticity" in names
    assert "stroke recovery" not in names


def test_search_topics_returns_description_match(session):
    get_or_create_topic(session, "cortical remapping", "neuroplasticity after injury")
    session.commit()
    results = search_topics(session, "neuroplasticity")
    assert any(r["name"] == "cortical remapping" for r in results)


def test_search_topics_respects_limit(session):
    for i in range(12):
        get_or_create_topic(session, f"topic {i}")
    session.commit()
    results = search_topics(session, "topic", limit=5)
    assert len(results) <= 5


def test_search_topics_returns_dict_shape(session):
    get_or_create_topic(session, "basal ganglia")
    session.commit()
    results = search_topics(session, "basal")
    assert {"id", "name", "description", "status"}.issubset(results[0].keys())


# --- get_topic_bundle ---

def test_get_topic_bundle_returns_empty_for_unknown(session):
    assert get_topic_bundle(session, 9999) == {}


def test_get_topic_bundle_returns_linked_concepts(session):
    topic = get_or_create_topic(session, "hippocampal plasticity")
    concept = get_or_create_concept(session, "LTP")
    session.flush()
    link_topic_concept(session, topic.id, concept.id)
    session.commit()
    bundle = get_topic_bundle(session, topic.id)
    assert bundle["topic"]["name"] == "hippocampal plasticity"
    assert any(c["name"] == "LTP" for c in bundle["concepts"])


def test_get_topic_bundle_returns_linked_papers(session):
    topic = get_or_create_topic(session, "stroke recovery")
    paper = _make_paper(session)
    session.flush()
    link_paper_topic(session, paper.id, topic.id)
    session.commit()
    bundle = get_topic_bundle(session, topic.id)
    assert any(p["title"] == "LTP Paper" for p in bundle["papers"])


def test_get_topic_bundle_returns_study_notes(session):
    topic = get_or_create_topic(session, "memory consolidation")
    session.flush()
    session.add(StudyNote(topic_id=topic.id, concept_tag="replay", tagged_at=_now()))
    session.commit()
    bundle = get_topic_bundle(session, topic.id)
    assert any(n["concept_tag"] == "replay" for n in bundle["study_notes"])


def test_get_topic_bundle_returns_dataset_packets(session):
    topic = get_or_create_topic(session, "fMRI analysis")
    packet = _make_packet(session)
    session.flush()
    link_packet_topic(session, packet.id, topic.id)
    session.commit()
    bundle = get_topic_bundle(session, topic.id)
    assert len(bundle["dataset_packets"]) == 1
    assert bundle["dataset_packets"][0]["source"] == "test"


def test_get_topic_bundle_excludes_resources_linked_to_other_topics(session):
    topic_a = get_or_create_topic(session, "topic A")
    topic_b = get_or_create_topic(session, "topic B")
    paper = _make_paper(session)
    session.flush()
    link_paper_topic(session, paper.id, topic_b.id)
    session.commit()
    bundle = get_topic_bundle(session, topic_a.id)
    assert len(bundle["papers"]) == 0


def test_get_topic_bundle_has_all_keys(session):
    topic = get_or_create_topic(session, "empty topic")
    session.commit()
    bundle = get_topic_bundle(session, topic.id)
    assert set(bundle.keys()) == {"topic", "concepts", "papers", "study_notes", "dataset_packets"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_topic_store.py -v
```

Expected: `ModuleNotFoundError` — `neurodb.db.topic_store` not found.

- [ ] **Step 3: Write the implementation**

Create `src/neurodb/db/topic_store.py`:

```python
"""DB epoch — topic, concept, and linking table operations."""
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from neurodb.schema import (
    Concept,
    DatasetPacketPaper,
    DatasetPacketTopic,
    DatasetResearchPacket,
    Paper,
    PaperConcept,
    PaperTopic,
    StudyNote,
    Topic,
    TopicConcept,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def get_or_create_topic(
    session: Session, name: str, description: str | None = None
) -> Topic:
    name = name.strip()
    existing = session.execute(
        select(Topic).where(Topic.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    now = _now()
    topic = Topic(
        name=name, description=description, status="active",
        created_at=now, updated_at=now,
    )
    session.add(topic)
    session.flush()
    return topic


def get_or_create_concept(
    session: Session, name: str, description: str | None = None
) -> Concept:
    name = name.strip()
    existing = session.execute(
        select(Concept).where(Concept.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    now = _now()
    concept = Concept(
        name=name, description=description, status="active",
        created_at=now, updated_at=now,
    )
    session.add(concept)
    session.flush()
    return concept


def link_paper_topic(session: Session, paper_id: int, topic_id: int) -> None:
    exists = session.execute(
        select(PaperTopic).where(
            PaperTopic.paper_id == paper_id, PaperTopic.topic_id == topic_id
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(PaperTopic(paper_id=paper_id, topic_id=topic_id))
        session.flush()


def link_paper_concept(session: Session, paper_id: int, concept_id: int) -> None:
    exists = session.execute(
        select(PaperConcept).where(
            PaperConcept.paper_id == paper_id, PaperConcept.concept_id == concept_id
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(PaperConcept(paper_id=paper_id, concept_id=concept_id))
        session.flush()


def link_topic_concept(session: Session, topic_id: int, concept_id: int) -> None:
    exists = session.execute(
        select(TopicConcept).where(
            TopicConcept.topic_id == topic_id, TopicConcept.concept_id == concept_id
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(TopicConcept(topic_id=topic_id, concept_id=concept_id))
        session.flush()


def link_packet_topic(session: Session, packet_id: int, topic_id: int) -> None:
    exists = session.execute(
        select(DatasetPacketTopic).where(
            DatasetPacketTopic.packet_id == packet_id,
            DatasetPacketTopic.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(DatasetPacketTopic(packet_id=packet_id, topic_id=topic_id))
        session.flush()


def link_packet_paper(session: Session, packet_id: int, paper_id: int) -> None:
    exists = session.execute(
        select(DatasetPacketPaper).where(
            DatasetPacketPaper.packet_id == packet_id,
            DatasetPacketPaper.paper_id == paper_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(DatasetPacketPaper(packet_id=packet_id, paper_id=paper_id))
        session.flush()


def search_topics(session: Session, query: str, limit: int = 10) -> list[dict]:
    q = f"%{query}%"
    rows = session.execute(
        select(Topic)
        .where(or_(Topic.name.ilike(q), Topic.description.ilike(q)))
        .limit(limit)
    ).scalars().all()
    return [
        {"id": t.id, "name": t.name, "description": t.description, "status": t.status}
        for t in rows
    ]


def get_topic_bundle(session: Session, topic_id: int) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        return {}

    concepts = session.execute(
        select(Concept)
        .join(TopicConcept, TopicConcept.concept_id == Concept.id)
        .where(TopicConcept.topic_id == topic_id)
    ).scalars().all()

    papers = session.execute(
        select(Paper)
        .join(PaperTopic, PaperTopic.paper_id == Paper.id)
        .where(PaperTopic.topic_id == topic_id)
    ).scalars().all()

    notes = session.execute(
        select(StudyNote).where(StudyNote.topic_id == topic_id)
    ).scalars().all()

    packets = session.execute(
        select(DatasetResearchPacket)
        .join(DatasetPacketTopic, DatasetPacketTopic.packet_id == DatasetResearchPacket.id)
        .where(DatasetPacketTopic.topic_id == topic_id)
    ).scalars().all()

    return {
        "topic": {"id": topic.id, "name": topic.name, "description": topic.description},
        "concepts": [
            {"id": c.id, "name": c.name, "description": c.description} for c in concepts
        ],
        "papers": [
            {"id": p.id, "title": p.title, "doi": p.doi, "status": p.status, "summary": p.summary}
            for p in papers
        ],
        "study_notes": [
            {"id": n.id, "note_text": n.note_text, "concept_tag": n.concept_tag, "tagged_at": n.tagged_at}
            for n in notes
        ],
        "dataset_packets": [
            {"id": pkt.id, "source": pkt.source, "source_id": pkt.source_id,
             "title": pkt.title, "usefulness_state": pkt.usefulness_state}
            for pkt in packets
        ],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_topic_store.py -v
```

Expected: all 20 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db/topic_store.py tests/unit/test_topic_store.py
git commit -m "feat: add topic_store helper — get_or_create, link, search_topics, get_topic_bundle"
```

---

## Task 7: Tutor agent extensions

**Files:**
- Modify: `src/neurodb/agents/tutor_agent.py`
- Modify: `tests/unit/test_tutor_agent.py`

- [ ] **Step 1: Write the failing tests**

Add the following to `tests/unit/test_tutor_agent.py`. At the top, update the import:

```python
from types import SimpleNamespace

from neurodb.agents.tutor_agent import NeuroTutorAgent, normalize_title
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.schema import Base, Paper, PaperTopic, Topic
```

Add these tests at the bottom of the file:

```python
def test_search_topics_and_get_topic_bundle_in_tool_list():
    names = {tool["name"] for tool in _agent()._get_active_tools()}
    assert "search_topics" in names
    assert "get_topic_bundle" in names


def test_queue_source_tool_schema_has_topics_field():
    tools = {t["name"]: t for t in _agent()._get_active_tools()}
    props = tools["queue_source"]["input_schema"]["properties"]
    assert "topics" in props
    assert props["topics"]["type"] == "array"


def test_search_topics_tool_returns_matching_topics():
    engine = _engine()
    from neurodb.db.topic_store import get_or_create_topic
    with Session(engine) as s:
        get_or_create_topic(s, "hippocampal plasticity")
        s.commit()
    agent = _agent(engine)
    block = SimpleNamespace(tool_name="search_topics", tool_input={"query": "hippocampal"})
    result = json.loads(agent._execute_tool_block(block))
    assert any(r["name"] == "hippocampal plasticity" for r in result)


def test_get_topic_bundle_tool_returns_bundle():
    engine = _engine()
    from neurodb.db.topic_store import get_or_create_topic
    with Session(engine) as s:
        topic = get_or_create_topic(s, "stroke recovery")
        s.commit()
        topic_id = topic.id
    agent = _agent(engine)
    block = SimpleNamespace(tool_name="get_topic_bundle", tool_input={"topic_id": topic_id})
    result = json.loads(agent._execute_tool_block(block))
    assert result["topic"]["name"] == "stroke recovery"


def test_queue_source_with_topics_creates_links():
    engine = _engine()
    agent = _agent(engine)
    result = json.loads(agent._execute_queue_source({
        "title": "LTP Review Paper",
        "source_type": "paper",
        "topic_context": "hippocampal plasticity",
        "topics": ["hippocampal plasticity", "synaptic potentiation"],
    }))
    assert result["status"] == "queued"
    paper_id = result["id"]
    with Session(engine) as s:
        links = s.query(PaperTopic).filter_by(paper_id=paper_id).all()
        assert len(links) == 2
        topic_ids = {link.topic_id for link in links}
        names = {s.get(Topic, tid).name for tid in topic_ids}
    assert names == {"hippocampal plasticity", "synaptic potentiation"}


def test_system_prompt_mentions_topic_retrieval_tools():
    prompt = _agent()._build_system_prompt()
    assert "search_topics" in prompt
    assert "get_topic_bundle" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_tutor_agent.py -v -k "topics or bundle"
```

Expected: FAIL — `search_topics`/`get_topic_bundle` not in tool list.

- [ ] **Step 3: Add new tools to _TUTOR_TOOLS in tutor_agent.py**

In `src/neurodb/agents/tutor_agent.py`, add to the `_TUTOR_TOOLS` list after the `queue_source` entry:

```python
    {
        "name": "search_topics",
        "description": "Search for topics in the NeuroDb knowledge base by name or description keyword.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword to search for."},
                "limit": {"type": "integer", "description": "Maximum results to return."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_topic_bundle",
        "description": (
            "Retrieve all related papers, concepts, study notes, and dataset packets "
            "for a topic. Use search_topics first to find the topic_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_id": {"type": "integer", "description": "Topic ID from search_topics."},
            },
            "required": ["topic_id"],
        },
    },
```

Add `"topics"` to the `queue_source` tool's `input_schema.properties`:

```python
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Topic names to link to this source.",
                },
```

- [ ] **Step 4: Update the system prompt**

In `_TUTOR_SYSTEM_PROMPT`, add after the existing last sentence:

```python
_TUTOR_SYSTEM_PROMPT = (
    "You are a neuroscience learning partner with access to a curated Knowledge Library, "
    "local study notes, local dataset tools, and your own training knowledge. "
    "For topic questions, call search_knowledge_library before relying on training "
    "knowledge alone. "
    "To retrieve local context for a topic, call search_topics to find the topic ID, "
    "then get_topic_bundle to retrieve related papers, concepts, notes, and datasets. "
    "Whenever you cite or recommend an external resource such as a paper, review, textbook, "
    "or website, call queue_source with the title, source type, and topic context so the user "
    "can review it later. To discover candidate learning resources, call search_literature. "
    "Never fabricate paper titles, DOIs, dataset IDs, counts, or source details. "
    "Format user-facing answers for the chat window: use concise prose, short lists, "
    "and simple Markdown tables only when they make comparison easier. Do not put raw "
    "tool JSON or debug traces in the final answer."
)
```

- [ ] **Step 5: Add dispatch and implementation methods**

In `_execute_tool_block`, add before the final `execute_tool(...)` fallback:

```python
        if block.tool_name == "search_topics":
            return self._execute_search_topics(block.tool_input)
        if block.tool_name == "get_topic_bundle":
            return self._execute_get_topic_bundle(block.tool_input)
```

Add two new methods to `NeuroTutorAgent`:

```python
    def _execute_search_topics(self, inputs: dict) -> str:
        from neurodb.db.topic_store import search_topics
        with get_session(self._engine) as session:
            results = search_topics(session, inputs["query"], limit=inputs.get("limit", 10))
        return json.dumps(results)

    def _execute_get_topic_bundle(self, inputs: dict) -> str:
        from neurodb.db.topic_store import get_topic_bundle
        with get_session(self._engine) as session:
            bundle = get_topic_bundle(session, inputs["topic_id"])
        return json.dumps(bundle)
```

- [ ] **Step 6: Extend _execute_queue_source to handle topics**

Replace the body of `_execute_queue_source` with:

```python
    def _execute_queue_source(self, inputs: dict) -> str:
        title = inputs["title"].strip()
        normalized = normalize_title(title)
        doi = (inputs.get("doi") or "").strip() or None
        topics = inputs.get("topics") or []

        with get_session(self._engine) as session:
            if doi:
                existing = session.query(Paper).filter_by(doi=doi).first()
            else:
                existing = session.query(Paper).filter_by(normalized_title=normalized).first()
            if existing is not None:
                return json.dumps({"status": "already_exists", "id": existing.id})

            row = Paper(
                title=title,
                normalized_title=normalized,
                doi=doi,
                url=(inputs.get("url") or None),
                source_type=inputs["source_type"],
                topic_context=inputs["topic_context"],
                status="pending",
                queued_at=datetime.now(UTC).isoformat(),
            )
            session.add(row)
            session.flush()
            paper_id = row.id

            if topics:
                from neurodb.db.topic_store import get_or_create_topic, link_paper_topic
                for topic_name in topics:
                    topic = get_or_create_topic(session, topic_name)
                    link_paper_topic(session, paper_id, topic.id)

            return json.dumps({"status": "queued", "id": paper_id})
```

- [ ] **Step 7: Run all tutor agent tests**

```bash
uv run pytest tests/unit/test_tutor_agent.py -v
```

Expected: all tests PASS (including the 6 new ones).

- [ ] **Step 8: Commit**

```bash
git add src/neurodb/agents/tutor_agent.py tests/unit/test_tutor_agent.py
git commit -m "feat: add search_topics and get_topic_bundle tools to NeuroTutorAgent; extend queue_source with topics"
```

---

## Task 8: Integration test

**Files:**
- Create: `tests/integration/test_phase2_topic_bundle.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_phase2_topic_bundle.py`:

```python
"""End-to-end Phase 2 integration: create topic → link concept, paper, packet, note → verify bundle."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.db.topic_store import (
    get_or_create_concept,
    get_or_create_topic,
    get_topic_bundle,
    link_packet_topic,
    link_paper_topic,
    link_topic_concept,
)
from neurodb.schema import (
    Base, DatasetIndex, DatasetResearchPacket, IngestRun, Paper, StudyNote,
)


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


def test_full_topic_bundle_round_trip(engine):
    with Session(engine) as session:
        # Create topic and concept
        topic = get_or_create_topic(session, "hippocampal plasticity",
                                    "memory formation and LTP")
        concept = get_or_create_concept(session, "LTP",
                                        "long-term potentiation")
        session.flush()
        link_topic_concept(session, topic.id, concept.id)

        # Approve a paper and link to topic
        paper = Paper(
            title="LTP and Memory Consolidation",
            normalized_title="ltp and memory consolidation",
            source_type="paper",
            topic_context="hippocampal plasticity",
            status="approved",
            queued_at=_now(),
        )
        session.add(paper)
        session.flush()
        link_paper_topic(session, paper.id, topic.id)

        # Create dataset packet and link to topic
        run = IngestRun(source="openneuro", run_at=_now(), version="1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds000001", run_id=run.id)
        session.add(idx)
        session.flush()
        packet = DatasetResearchPacket(
            index_id=idx.id, source="openneuro", source_id="ds000001",
            title="Hippocampal fMRI Study",
            usefulness_state="partial",
            supported_workflows_json="[]", unsupported_workflows_json="[]",
            missing_context_json="[]", provenance_json="{}", confidence_json="{}",
            harvested_at=_now(), run_id=run.id,
        )
        session.add(packet)
        session.flush()
        link_packet_topic(session, packet.id, topic.id)

        # Add study note anchored to topic
        note = StudyNote(
            topic_id=topic.id,
            concept_tag="LTP",
            note_text="Key mechanism for memory encoding",
            tagged_at=_now(),
        )
        session.add(note)
        session.commit()

        bundle = get_topic_bundle(session, topic.id)

    assert bundle["topic"]["name"] == "hippocampal plasticity"
    assert any(c["name"] == "LTP" for c in bundle["concepts"])
    assert any(p["title"] == "LTP and Memory Consolidation" for p in bundle["papers"])
    assert any(n["note_text"] == "Key mechanism for memory encoding"
               for n in bundle["study_notes"])
    assert any(pkt["source"] == "openneuro" for pkt in bundle["dataset_packets"])


def test_study_note_anchored_to_topic_without_dataset(engine):
    with Session(engine) as session:
        topic = get_or_create_topic(session, "cortical remapping")
        session.flush()
        note = StudyNote(
            topic_id=topic.id,
            concept_tag="plasticity",
            note_text="Cortex reorganizes after lesion",
            tagged_at=_now(),
        )
        session.add(note)
        session.commit()
        bundle = get_topic_bundle(session, topic.id)
    assert len(bundle["study_notes"]) == 1
    assert bundle["study_notes"][0]["note_text"] == "Cortex reorganizes after lesion"


def test_unlinked_resources_do_not_appear_in_bundle(engine):
    with Session(engine) as session:
        topic_a = get_or_create_topic(session, "topic A")
        topic_b = get_or_create_topic(session, "topic B")
        paper = Paper(
            title="Only B Paper", normalized_title="only b paper",
            source_type="paper", topic_context="B", status="approved",
            queued_at=_now(),
        )
        session.add(paper)
        session.flush()
        link_paper_topic(session, paper.id, topic_b.id)
        session.commit()
        bundle = get_topic_bundle(session, topic_a.id)
    assert len(bundle["papers"]) == 0
    assert len(bundle["concepts"]) == 0
    assert len(bundle["study_notes"]) == 0
    assert len(bundle["dataset_packets"]) == 0
```

- [ ] **Step 2: Run the integration test**

```bash
uv run pytest tests/integration/test_phase2_topic_bundle.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 3: Run full suite to confirm clean baseline**

```bash
uv run pytest tests/ -q
```

Expected: all pre-existing tests pass; 9 pre-existing failures in `test_model_config.py` / `test_task_router.py` / `test_knowledge_library_page.py` remain (these are routing-config failures unrelated to Phase 2 — tracked in `docs/testLog.md`).

- [ ] **Step 4: Update projectStatus.md**

In `docs/projectStatus.md`, update the DB row in the Epoch Status table to note Phase 2 implementation in progress, and update the Active focus line.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_phase2_topic_bundle.py docs/projectStatus.md
git commit -m "test: Phase 2 integration tests — full topic bundle round-trip"
```
