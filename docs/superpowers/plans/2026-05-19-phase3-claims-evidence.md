# Phase 3 — Claims, Evidence Links, and Research Gaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `claims`, `evidence_links`, and `research_gaps` tables with a `claim_store` helper and six new research agent tools so hypotheses can be grounded in structured local evidence rather than free-text.

**Architecture:** Three new ORM models live in `schema.py` and are owned by a new `claim_store.py` DB-epoch helper that follows the same session-in, dict-out pattern as `topic_store.py`. The research agent dispatches six new tools as thin wrappers around the helper, with lazy imports to avoid circular imports. The migration script handles all ALTER TABLE work idempotently against DuckDB.

**Tech Stack:** Python, SQLAlchemy ORM, DuckDB (runtime), SQLite in-memory (unit tests), pytest, FastAPI test client.

---

## File Map

| Action | Path |
|--------|------|
| Modify | `src/neurodb/schema.py` — add Claim, EvidenceLink, ResearchGap; add topic_id to ResearchQuestion; make evidence/datasets/confounds_json nullable on ResearchHypothesis |
| Create | `src/neurodb/db/claim_store.py` — all claim, evidence link, gap, and bundle read/write |
| Create | `scripts/migrate_phase3_claims_evidence.py` — DuckDB migration script |
| Create | `tests/unit/test_schema_claims.py` — ORM structure and CheckConstraint tests |
| Create | `tests/unit/test_claim_store.py` — unit tests for claim_store helper |
| Create | `tests/unit/test_migrate_phase3.py` — DuckDB in-memory migration tests |
| Modify | `tests/unit/test_research_agent.py` — add tests for 6 new tools |
| Modify | `src/neurodb/agents/research_agent.py` — 6 new tools + system prompt addition + draft_hypothesis evidence optional |
| Create | `tests/integration/test_phase3_evidence_bundle.py` — end-to-end integration test |
| Modify | `docs/projectStatus.md` — update phase row, test count, add manual test plan reference |

---

## Task 1: Schema — Claim, EvidenceLink, ResearchGap + ORM modifications

**Files:**
- Create tests: `tests/unit/test_schema_claims.py`
- Modify: `src/neurodb/schema.py`

- [ ] **Step 1: Write the failing schema tests**

Create `tests/unit/test_schema_claims.py`:

```python
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Claim, EvidenceLink, ResearchGap, ResearchHypothesis, ResearchQuestion


def _engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


# --- Table structure ---

def test_claims_table_exists():
    assert "claims" in inspect(_engine()).get_table_names()


def test_evidence_links_table_exists():
    assert "evidence_links" in inspect(_engine()).get_table_names()


def test_research_gaps_table_exists():
    assert "research_gaps" in inspect(_engine()).get_table_names()


def test_claims_has_expected_columns():
    cols = {c.key for c in Claim.__table__.columns}
    assert {"id", "paper_id", "text", "claim_type", "status", "created_at", "updated_at"} <= cols


def test_evidence_links_has_expected_columns():
    cols = {c.key for c in EvidenceLink.__table__.columns}
    assert {
        "id", "hypothesis_id", "claim_id", "paper_id",
        "packet_id", "note_id", "link_type", "created_at",
    } <= cols


def test_research_gaps_has_expected_columns():
    cols = {c.key for c in ResearchGap.__table__.columns}
    assert {
        "id", "question_id", "hypothesis_id", "description",
        "gap_type", "status", "created_at", "updated_at",
    } <= cols


def test_research_question_has_topic_id():
    cols = {c.key for c in ResearchQuestion.__table__.columns}
    assert "topic_id" in cols


# --- EvidenceLink CheckConstraint ---

def test_evidence_link_rejects_zero_sources():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports", created_at="2026-01-01T00:00:00",
        ))
        with pytest.raises(IntegrityError):
            session.flush()


def test_evidence_link_rejects_two_sources():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports",
            claim_id=1, paper_id=2,
            created_at="2026-01-01T00:00:00",
        ))
        with pytest.raises(IntegrityError):
            session.flush()


def test_evidence_link_accepts_claim_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports", claim_id=1,
            created_at="2026-01-01T00:00:00",
        ))
        session.flush()  # must not raise


def test_evidence_link_accepts_paper_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports", paper_id=1,
            created_at="2026-01-01T00:00:00",
        ))
        session.flush()


def test_evidence_link_accepts_packet_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports", packet_id=1,
            created_at="2026-01-01T00:00:00",
        ))
        session.flush()


def test_evidence_link_accepts_note_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports", note_id=1,
            created_at="2026-01-01T00:00:00",
        ))
        session.flush()


# --- ResearchGap CheckConstraint ---

def test_research_gap_rejects_both_anchors_null():
    engine = _engine()
    with Session(engine) as session:
        session.add(ResearchGap(
            description="Missing data", gap_type="missing_dataset",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        ))
        with pytest.raises(IntegrityError):
            session.flush()


def test_research_gap_accepts_question_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(ResearchGap(
            question_id=1, description="Need more data", gap_type="missing_dataset",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        ))
        session.flush()


def test_research_gap_accepts_hypothesis_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(ResearchGap(
            hypothesis_id=1, description="Need more data", gap_type="missing_paper",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        ))
        session.flush()


# --- ResearchHypothesis nullable fields ---

def test_research_hypothesis_accepts_null_evidence_json():
    engine = _engine()
    with Session(engine) as session:
        session.add(ResearchHypothesis(
            title="Test", mechanism="mechanism",
            evidence_json=None, datasets_json=None, confounds_json=None,
            predictions_json="[]", limitations="none",
            status="draft",
            created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        ))
        session.flush()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_schema_claims.py -v
```

Expected: most tests FAIL — `ImportError` on `Claim`, `EvidenceLink`, `ResearchGap`; `AssertionError` on column checks.

- [ ] **Step 3: Add new models to `src/neurodb/schema.py`**

After the `DatasetPacketPaper` class (end of file), add:

```python
class Claim(Base):
    """Paper-sourced claim awaiting review — candidate, approved, or rejected."""
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, Sequence("claims_id_seq"), primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="candidate")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class EvidenceLink(Base):
    """Structured evidence link from a hypothesis to a claim, paper, dataset packet, or study note.

    CheckConstraint enforces exactly one of (claim_id, paper_id, packet_id, note_id) non-null.
    """
    __tablename__ = "evidence_links"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN claim_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN paper_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN packet_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN note_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_evidence_links_one_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("evidence_links_id_seq"), primary_key=True)
    hypothesis_id: Mapped[int] = mapped_column(
        ForeignKey("research_hypotheses.id"), nullable=False, index=True
    )
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id"), nullable=True)
    packet_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataset_research_packets.id"), nullable=True
    )
    note_id: Mapped[int | None] = mapped_column(ForeignKey("study_notes.id"), nullable=True)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ResearchGap(Base):
    """Named evidence gap anchored to a research question or hypothesis (or both)."""
    __tablename__ = "research_gaps"
    __table_args__ = (
        CheckConstraint(
            "question_id IS NOT NULL OR hypothesis_id IS NOT NULL",
            name="ck_research_gaps_one_anchor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("research_gaps_id_seq"), primary_key=True)
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_questions.id"), nullable=True
    )
    hypothesis_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_hypotheses.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    gap_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

In the `ResearchQuestion` class, add `topic_id` after `updated_at`:

```python
topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
```

In the `ResearchHypothesis` class, change these three fields from NOT NULL to nullable:

```python
evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
datasets_json: Mapped[str | None] = mapped_column(Text, nullable=True)
confounds_json: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_schema_claims.py -v
```

Expected: all tests PASS.

Also run the full suite to check for regressions:

```bash
uv run pytest tests/ -q
```

Expected: no new failures beyond the 9 pre-existing config-routing failures.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_schema_claims.py
git commit -m "feat: add Claim, EvidenceLink, ResearchGap schema; topic_id on ResearchQuestion; nullable evidence fields"
```

---

## Task 2: Migration script

**Files:**
- Create tests: `tests/unit/test_migrate_phase3.py`
- Create: `scripts/migrate_phase3_claims_evidence.py`

- [ ] **Step 1: Write the failing migration tests**

Create `tests/unit/test_migrate_phase3.py`:

```python
"""Migration tests use DuckDB in-memory — ALTER COLUMN DROP NOT NULL is DuckDB-only syntax."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

_PRE_MIGRATION_STMTS = [
    "CREATE SEQUENCE IF NOT EXISTS research_questions_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS research_questions (
        id INTEGER DEFAULT nextval('research_questions_id_seq') PRIMARY KEY,
        question TEXT NOT NULL,
        topic_context TEXT NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'open',
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL
    )""",
    "CREATE SEQUENCE IF NOT EXISTS research_hypotheses_id_seq START 1",
    """CREATE TABLE IF NOT EXISTS research_hypotheses (
        id INTEGER DEFAULT nextval('research_hypotheses_id_seq') PRIMARY KEY,
        question_id INTEGER,
        title TEXT NOT NULL,
        mechanism TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        predictions_json TEXT NOT NULL,
        datasets_json TEXT NOT NULL,
        confounds_json TEXT NOT NULL,
        limitations TEXT NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'draft',
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL
    )""",
]


@pytest.fixture
def pre_migration_engine():
    engine = create_engine("duckdb:///:memory:")
    with engine.begin() as conn:
        for stmt in _PRE_MIGRATION_STMTS:
            conn.execute(text(stmt))
    yield engine
    engine.dispose()


def _get_tables(engine) -> set:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='main'"
            )
        ).fetchall()
    return {r[0] for r in rows}


def _get_columns(engine, table: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name, is_nullable FROM information_schema.columns "
                "WHERE table_name = :t ORDER BY ordinal_position"
            ),
            {"t": table},
        ).fetchall()
    return [{"name": r[0], "nullable": r[1] == "YES"} for r in rows]


def test_migration_creates_claims_table(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    assert "claims" in _get_tables(pre_migration_engine)


def test_migration_creates_evidence_links_table(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    assert "evidence_links" in _get_tables(pre_migration_engine)


def test_migration_creates_research_gaps_table(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    assert "research_gaps" in _get_tables(pre_migration_engine)


def test_migration_adds_topic_id_to_research_questions(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    cols = {c["name"] for c in _get_columns(pre_migration_engine, "research_questions")}
    assert "topic_id" in cols


def test_migration_makes_evidence_json_nullable(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    col = next(
        c for c in _get_columns(pre_migration_engine, "research_hypotheses")
        if c["name"] == "evidence_json"
    )
    assert col["nullable"] is True


def test_migration_makes_datasets_json_nullable(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    col = next(
        c for c in _get_columns(pre_migration_engine, "research_hypotheses")
        if c["name"] == "datasets_json"
    )
    assert col["nullable"] is True


def test_migration_makes_confounds_json_nullable(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    col = next(
        c for c in _get_columns(pre_migration_engine, "research_hypotheses")
        if c["name"] == "confounds_json"
    )
    assert col["nullable"] is True


def test_migration_is_idempotent(pre_migration_engine):
    from migrate_phase3_claims_evidence import run_migration
    run_migration(pre_migration_engine)
    run_migration(pre_migration_engine)  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_migrate_phase3.py -v
```

Expected: all tests FAIL with `ModuleNotFoundError: No module named 'migrate_phase3_claims_evidence'`.

- [ ] **Step 3: Write the migration script**

Create `scripts/migrate_phase3_claims_evidence.py`:

```python
#!/usr/bin/env python
"""Phase 3 migration: add claims, evidence_links, research_gaps; add topic_id to
research_questions; make evidence_json, datasets_json, confounds_json nullable on
research_hypotheses.

Safe to re-run. Each step checks current state before executing.

Usage:
    uv run scripts/migrate_phase3_claims_evidence.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, text

from neurodb.schema import Base


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() > 0


def _table_exists(conn, table: str) -> bool:
    result = conn.execute(
        text("SELECT count(*) FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
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
    # Step 1: create new tables (claims, evidence_links, research_gaps) and any
    # other ORM-defined tables not yet in the DB. Skips tables that already exist.
    Base.metadata.create_all(engine, checkfirst=True)
    print("✓ create_all complete — new tables created if missing")

    with engine.begin() as conn:
        # Step 2: add topic_id FK to research_questions
        if not _column_exists(conn, "research_questions", "topic_id"):
            # DuckDB does not support ADD COLUMN with inline REFERENCES.
            # FK semantics are enforced at the ORM level.
            conn.execute(
                text("ALTER TABLE research_questions ADD COLUMN topic_id INTEGER")
            )
            print("✓ Added research_questions.topic_id")
        else:
            print("✓ research_questions.topic_id already present — skip")

        # Steps 3–5: make evidence fields nullable on research_hypotheses
        for col in ["evidence_json", "datasets_json", "confounds_json"]:
            if _table_exists(conn, "research_hypotheses") and not _is_nullable(
                conn, "research_hypotheses", col
            ):
                conn.execute(
                    text(
                        f"ALTER TABLE research_hypotheses ALTER COLUMN {col} DROP NOT NULL"
                    )
                )
                print(f"✓ research_hypotheses.{col} is now nullable")
            else:
                print(f"✓ research_hypotheses.{col} already nullable — skip")


if __name__ == "__main__":
    db_path = os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb")
    engine = create_engine(f"duckdb:///{db_path}")
    run_migration(engine)
    print("\nMigration complete.")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_migrate_phase3.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_phase3_claims_evidence.py tests/unit/test_migrate_phase3.py
git commit -m "feat: add Phase 3 migration script — claims, evidence_links, research_gaps, nullable evidence fields"
```

---

## Task 3: `claim_store` helper

**Files:**
- Create tests: `tests/unit/test_claim_store.py`
- Create: `src/neurodb/db/claim_store.py`

- [ ] **Step 1: Write the failing claim_store tests**

Create `tests/unit/test_claim_store.py`:

```python
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import (
    Base, Claim, DatasetIndex, DatasetResearchPacket, IngestRun,
    Paper, PaperTopic, ResearchHypothesis, ResearchQuestion, StudyNote, Topic,
)
from neurodb.db.topic_store import get_or_create_topic, link_paper_topic
from neurodb.db.claim_store import (
    add_evidence_link,
    add_gap,
    create_claim,
    get_approved_claims_for_topic,
    get_claims_for_paper,
    get_evidence_links,
    get_gaps,
    get_question_bundle,
    resolve_gap,
    update_claim_status,
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


def _make_paper(session, doi="10.1234/test"):
    paper = Paper(
        title="LTP Study", normalized_title=f"ltp study {doi}",
        doi=doi, source_type="paper", topic_context="plasticity",
        status="approved", queued_at=_now(),
    )
    session.add(paper)
    session.flush()
    return paper


def _make_hypothesis(session, question_id=None):
    h = ResearchHypothesis(
        question_id=question_id, title="Test hypothesis",
        mechanism="LTP drives learning.", predictions_json="[]",
        limitations="draft", status="draft",
        created_at=_now(), updated_at=_now(),
    )
    session.add(h)
    session.flush()
    return h


def _make_question(session, topic_id=None):
    q = ResearchQuestion(
        question="Does LTP drive learning?",
        topic_context="plasticity",
        topic_id=topic_id,
        status="open",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(q)
    session.flush()
    return q


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


# --- create_claim ---

def test_create_claim_persists_with_candidate_status(session):
    paper = _make_paper(session)
    claim = create_claim(session, paper.id, "LTP increases synaptic weight.", "finding")
    session.commit()
    assert claim.id is not None
    assert claim.status == "candidate"
    assert claim.claim_type == "finding"


def test_create_claim_raises_for_unknown_type(session):
    paper = _make_paper(session)
    with pytest.raises(ValueError, match="Unknown claim_type"):
        create_claim(session, paper.id, "Some claim.", "invalid_type")


# --- update_claim_status ---

def test_update_claim_status_approves(session):
    paper = _make_paper(session)
    claim = create_claim(session, paper.id, "Key finding.", "finding")
    session.flush()
    result = update_claim_status(session, claim.id, "approved")
    assert result == {"id": claim.id, "status": "approved"}
    assert claim.status == "approved"


def test_update_claim_status_rejects(session):
    paper = _make_paper(session)
    claim = create_claim(session, paper.id, "Dubious claim.", "finding")
    session.flush()
    result = update_claim_status(session, claim.id, "rejected")
    assert result["status"] == "rejected"


def test_update_claim_status_raises_for_unknown_status(session):
    paper = _make_paper(session)
    claim = create_claim(session, paper.id, "Some finding.", "finding")
    session.flush()
    with pytest.raises(ValueError, match="Unknown status"):
        update_claim_status(session, claim.id, "published")


# --- get_claims_for_paper ---

def test_get_claims_for_paper_returns_only_that_paper(session):
    paper_a = _make_paper(session, doi="10.1/a")
    paper_b = _make_paper(session, doi="10.1/b")
    create_claim(session, paper_a.id, "Claim A.", "finding")
    create_claim(session, paper_b.id, "Claim B.", "limitation")
    session.flush()

    results = get_claims_for_paper(session, paper_a.id)
    assert len(results) == 1
    assert results[0]["text"] == "Claim A."


def test_get_claims_for_paper_returns_dict_shape(session):
    paper = _make_paper(session)
    create_claim(session, paper.id, "Finding.", "finding")
    session.flush()
    results = get_claims_for_paper(session, paper.id)
    assert {"id", "text", "claim_type", "status", "paper_id"}.issubset(results[0].keys())


# --- get_approved_claims_for_topic ---

def test_get_approved_claims_for_topic_returns_only_approved(session):
    paper = _make_paper(session)
    topic = get_or_create_topic(session, "plasticity")
    session.flush()
    link_paper_topic(session, paper.id, topic.id)

    c_approved = create_claim(session, paper.id, "LTP is real.", "finding")
    c_candidate = create_claim(session, paper.id, "Maybe LTP matters.", "question")
    update_claim_status(session, c_approved.id, "approved")
    session.flush()

    results = get_approved_claims_for_topic(session, topic.id)
    texts = [r["text"] for r in results]
    assert "LTP is real." in texts
    assert "Maybe LTP matters." not in texts


def test_get_approved_claims_for_topic_includes_paper_title(session):
    paper = _make_paper(session)
    topic = get_or_create_topic(session, "memory")
    session.flush()
    link_paper_topic(session, paper.id, topic.id)
    claim = create_claim(session, paper.id, "Key finding.", "finding")
    update_claim_status(session, claim.id, "approved")
    session.flush()

    results = get_approved_claims_for_topic(session, topic.id)
    assert results[0]["paper_title"] == "LTP Study"


# --- add_evidence_link ---

def test_add_evidence_link_with_claim(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    claim = create_claim(session, paper.id, "Finding.", "finding")
    session.flush()

    link = add_evidence_link(session, hyp.id, "supports", claim_id=claim.id)
    assert link.id is not None
    assert link.claim_id == claim.id
    assert link.link_type == "supports"


def test_add_evidence_link_idempotent(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    claim = create_claim(session, paper.id, "Finding.", "finding")
    session.flush()

    link1 = add_evidence_link(session, hyp.id, "supports", claim_id=claim.id)
    link2 = add_evidence_link(session, hyp.id, "supports", claim_id=claim.id)
    assert link1.id == link2.id


def test_add_evidence_link_raises_for_zero_sources(session):
    hyp = _make_hypothesis(session)
    session.flush()
    with pytest.raises(ValueError, match="Exactly one source"):
        add_evidence_link(session, hyp.id, "supports")


def test_add_evidence_link_raises_for_two_sources(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    claim = create_claim(session, paper.id, "Finding.", "finding")
    session.flush()
    with pytest.raises(ValueError, match="Exactly one source"):
        add_evidence_link(session, hyp.id, "supports", claim_id=claim.id, paper_id=paper.id)


def test_add_evidence_link_raises_for_unknown_link_type(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    claim = create_claim(session, paper.id, "Finding.", "finding")
    session.flush()
    with pytest.raises(ValueError, match="Unknown link_type"):
        add_evidence_link(session, hyp.id, "proves", claim_id=claim.id)


# --- get_evidence_links ---

def test_get_evidence_links_returns_correct_shape(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    claim = create_claim(session, paper.id, "A finding.", "finding")
    session.flush()
    add_evidence_link(session, hyp.id, "supports", claim_id=claim.id)
    session.flush()

    links = get_evidence_links(session, hyp.id)
    assert len(links) == 1
    assert {"id", "link_type", "source_type", "source_id", "summary"}.issubset(links[0].keys())
    assert links[0]["source_type"] == "claim"
    assert links[0]["source_id"] == claim.id


def test_get_evidence_links_returns_empty_when_none(session):
    hyp = _make_hypothesis(session)
    session.flush()
    assert get_evidence_links(session, hyp.id) == []


def test_get_evidence_links_source_type_for_paper(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    session.flush()
    add_evidence_link(session, hyp.id, "contextualizes", paper_id=paper.id)
    session.flush()

    links = get_evidence_links(session, hyp.id)
    assert links[0]["source_type"] == "paper"


def test_get_evidence_links_source_type_for_dataset(session):
    packet = _make_packet(session)
    hyp = _make_hypothesis(session)
    session.flush()
    add_evidence_link(session, hyp.id, "contextualizes", packet_id=packet.id)
    session.flush()

    links = get_evidence_links(session, hyp.id)
    assert links[0]["source_type"] == "dataset"


def test_get_evidence_links_source_type_for_note(session):
    hyp = _make_hypothesis(session)
    note = StudyNote(note_id_anchor=None, concept_tag="LTP", tagged_at=_now())
    # Note needs one anchor; use hypothesis_id itself as concept_tag only
    # Create a minimal note anchored to a paper FK (dummy, SQLite doesn't enforce FK)
    note = StudyNote(paper_id=1, concept_tag="LTP", tagged_at=_now())
    session.add(note)
    session.flush()
    add_evidence_link(session, hyp.id, "supports", note_id=note.id)
    session.flush()

    links = get_evidence_links(session, hyp.id)
    assert links[0]["source_type"] == "note"


# --- add_gap ---

def test_add_gap_persists_with_open_status(session):
    q = _make_question(session)
    gap = add_gap(session, "No fMRI data.", "missing_dataset", question_id=q.id)
    session.flush()
    assert gap.id is not None
    assert gap.status == "open"


def test_add_gap_raises_when_both_anchors_none(session):
    with pytest.raises(ValueError, match="At least one of"):
        add_gap(session, "No data.", "missing_dataset")


def test_add_gap_raises_for_unknown_gap_type(session):
    q = _make_question(session)
    session.flush()
    with pytest.raises(ValueError, match="Unknown gap_type"):
        add_gap(session, "No data.", "missing_everything", question_id=q.id)


# --- resolve_gap ---

def test_resolve_gap_changes_status(session):
    q = _make_question(session)
    gap = add_gap(session, "No data.", "missing_paper", question_id=q.id)
    session.flush()

    result = resolve_gap(session, gap.id)
    assert result == {"id": gap.id, "status": "resolved"}
    assert gap.status == "resolved"


def test_resolve_gap_raises_for_unknown_id(session):
    with pytest.raises(ValueError, match="not found"):
        resolve_gap(session, 9999)


# --- get_gaps ---

def test_get_gaps_filters_by_question_id(session):
    q_a = _make_question(session)
    q_b = _make_question(session)
    session.flush()
    add_gap(session, "Gap A.", "missing_dataset", question_id=q_a.id)
    add_gap(session, "Gap B.", "missing_paper", question_id=q_b.id)
    session.flush()

    gaps = get_gaps(session, question_id=q_a.id)
    assert len(gaps) == 1
    assert gaps[0]["description"] == "Gap A."


def test_get_gaps_filters_by_hypothesis_id(session):
    h = _make_hypothesis(session)
    session.flush()
    add_gap(session, "Hyp gap.", "unsupported_claim", hypothesis_id=h.id)
    session.flush()

    gaps = get_gaps(session, hypothesis_id=h.id)
    assert len(gaps) == 1
    assert gaps[0]["description"] == "Hyp gap."


def test_get_gaps_returns_open_and_resolved(session):
    q = _make_question(session)
    g1 = add_gap(session, "Open.", "missing_dataset", question_id=q.id)
    g2 = add_gap(session, "Resolved.", "missing_paper", question_id=q.id)
    session.flush()
    resolve_gap(session, g2.id)
    session.flush()

    gaps = get_gaps(session, question_id=q.id)
    statuses = {g["status"] for g in gaps}
    assert "open" in statuses
    assert "resolved" in statuses


# --- get_question_bundle ---

def test_get_question_bundle_returns_empty_for_unknown(session):
    assert get_question_bundle(session, 9999) == {}


def test_get_question_bundle_returns_correct_shape(session):
    topic = get_or_create_topic(session, "hippocampal plasticity")
    session.flush()
    q = _make_question(session, topic_id=topic.id)
    h = _make_hypothesis(session, question_id=q.id)
    session.flush()
    add_gap(session, "Need more data.", "missing_dataset", question_id=q.id)
    session.flush()

    bundle = get_question_bundle(session, q.id)

    assert set(bundle.keys()) == {"question", "topic", "hypotheses", "claims", "gaps"}
    assert bundle["question"]["id"] == q.id
    assert bundle["topic"]["name"] == "hippocampal plasticity"
    assert any(h_item["id"] == h.id for h_item in bundle["hypotheses"])
    assert len(bundle["gaps"]) == 1


def test_get_question_bundle_topic_is_none_when_no_topic_id(session):
    q = _make_question(session)
    session.flush()
    bundle = get_question_bundle(session, q.id)
    assert bundle["topic"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_claim_store.py -v
```

Expected: all tests FAIL with `ImportError: cannot import name 'create_claim' from 'neurodb.db.claim_store'`.

- [ ] **Step 3: Write `src/neurodb/db/claim_store.py`**

Create `src/neurodb/db/claim_store.py`:

```python
"""DB epoch — claim, evidence link, and research gap operations."""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from neurodb.schema import (
    Claim,
    DatasetResearchPacket,
    EvidenceLink,
    Paper,
    PaperTopic,
    ResearchGap,
    ResearchHypothesis,
    ResearchQuestion,
    StudyNote,
    Topic,
)

_CLAIM_TYPES = {"finding", "limitation", "method", "question"}
_CLAIM_STATUSES = {"candidate", "approved", "rejected"}
_LINK_TYPES = {"supports", "contradicts", "contextualizes"}
_GAP_TYPES = {
    "missing_dataset", "missing_paper", "missing_evidence",
    "unsupported_claim", "other",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

def create_claim(session: Session, paper_id: int, text: str, claim_type: str) -> Claim:
    if claim_type not in _CLAIM_TYPES:
        raise ValueError(f"Unknown claim_type: {claim_type!r}. Valid: {sorted(_CLAIM_TYPES)}")
    now = _now()
    claim = Claim(
        paper_id=paper_id, text=text, claim_type=claim_type,
        status="candidate", created_at=now, updated_at=now,
    )
    session.add(claim)
    session.flush()
    return claim


def update_claim_status(session: Session, claim_id: int, status: str) -> dict:
    if status not in _CLAIM_STATUSES:
        raise ValueError(f"Unknown status: {status!r}. Valid: {sorted(_CLAIM_STATUSES)}")
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise ValueError(f"Claim {claim_id} not found")
    claim.status = status
    claim.updated_at = _now()
    session.flush()
    return {"id": claim.id, "status": claim.status}


def get_claims_for_paper(session: Session, paper_id: int) -> list[dict]:
    rows = session.execute(
        select(Claim).where(Claim.paper_id == paper_id)
    ).scalars().all()
    return [
        {
            "id": c.id, "text": c.text, "claim_type": c.claim_type,
            "status": c.status, "paper_id": c.paper_id,
        }
        for c in rows
    ]


def get_approved_claims_for_topic(session: Session, topic_id: int) -> list[dict]:
    rows = session.execute(
        select(Claim, Paper)
        .join(Paper, Paper.id == Claim.paper_id)
        .join(PaperTopic, PaperTopic.paper_id == Paper.id)
        .where(PaperTopic.topic_id == topic_id)
        .where(Claim.status == "approved")
    ).all()
    return [
        {
            "id": c.id, "text": c.text, "claim_type": c.claim_type,
            "paper_id": c.paper_id, "paper_title": p.title,
        }
        for c, p in rows
    ]


# ---------------------------------------------------------------------------
# Evidence links
# ---------------------------------------------------------------------------

def add_evidence_link(
    session: Session,
    hypothesis_id: int,
    link_type: str,
    *,
    claim_id: int | None = None,
    paper_id: int | None = None,
    packet_id: int | None = None,
    note_id: int | None = None,
) -> EvidenceLink:
    if link_type not in _LINK_TYPES:
        raise ValueError(f"Unknown link_type: {link_type!r}. Valid: {sorted(_LINK_TYPES)}")
    provided = sum(x is not None for x in [claim_id, paper_id, packet_id, note_id])
    if provided != 1:
        raise ValueError(
            f"Exactly one source FK must be provided; got {provided}. "
            "Pass one of: claim_id, paper_id, packet_id, note_id."
        )

    # Idempotency: return existing link with same (hypothesis, link_type, source)
    existing = session.execute(
        select(EvidenceLink).where(
            EvidenceLink.hypothesis_id == hypothesis_id,
            EvidenceLink.link_type == link_type,
            EvidenceLink.claim_id == claim_id if claim_id is not None
            else EvidenceLink.claim_id.is_(None),
            EvidenceLink.paper_id == paper_id if paper_id is not None
            else EvidenceLink.paper_id.is_(None),
            EvidenceLink.packet_id == packet_id if packet_id is not None
            else EvidenceLink.packet_id.is_(None),
            EvidenceLink.note_id == note_id if note_id is not None
            else EvidenceLink.note_id.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    link = EvidenceLink(
        hypothesis_id=hypothesis_id,
        link_type=link_type,
        claim_id=claim_id,
        paper_id=paper_id,
        packet_id=packet_id,
        note_id=note_id,
        created_at=_now(),
    )
    session.add(link)
    session.flush()
    return link


def get_evidence_links(session: Session, hypothesis_id: int) -> list[dict]:
    rows = session.execute(
        select(EvidenceLink).where(EvidenceLink.hypothesis_id == hypothesis_id)
    ).scalars().all()
    result = []
    for lnk in rows:
        if lnk.claim_id is not None:
            source_type, source_id = "claim", lnk.claim_id
            obj = session.get(Claim, lnk.claim_id)
            summary = (obj.text[:80] if obj else f"claim:{lnk.claim_id}")
        elif lnk.paper_id is not None:
            source_type, source_id = "paper", lnk.paper_id
            obj = session.get(Paper, lnk.paper_id)
            summary = (obj.title[:80] if obj else f"paper:{lnk.paper_id}")
        elif lnk.packet_id is not None:
            source_type, source_id = "dataset", lnk.packet_id
            obj = session.get(DatasetResearchPacket, lnk.packet_id)
            summary = ((obj.title or obj.source_id)[:80] if obj else f"packet:{lnk.packet_id}")
        else:
            source_type, source_id = "note", lnk.note_id
            obj = session.get(StudyNote, lnk.note_id)
            summary = ((obj.note_text or obj.concept_tag)[:80] if obj else f"note:{lnk.note_id}")
        result.append({
            "id": lnk.id,
            "link_type": lnk.link_type,
            "source_type": source_type,
            "source_id": source_id,
            "summary": summary,
        })
    return result


# ---------------------------------------------------------------------------
# Research gaps
# ---------------------------------------------------------------------------

def add_gap(
    session: Session,
    description: str,
    gap_type: str,
    *,
    question_id: int | None = None,
    hypothesis_id: int | None = None,
) -> ResearchGap:
    if gap_type not in _GAP_TYPES:
        raise ValueError(f"Unknown gap_type: {gap_type!r}. Valid: {sorted(_GAP_TYPES)}")
    if question_id is None and hypothesis_id is None:
        raise ValueError("At least one of question_id or hypothesis_id must be provided")
    now = _now()
    gap = ResearchGap(
        question_id=question_id,
        hypothesis_id=hypothesis_id,
        description=description,
        gap_type=gap_type,
        status="open",
        created_at=now,
        updated_at=now,
    )
    session.add(gap)
    session.flush()
    return gap


def resolve_gap(session: Session, gap_id: int) -> dict:
    gap = session.get(ResearchGap, gap_id)
    if gap is None:
        raise ValueError(f"ResearchGap {gap_id} not found")
    gap.status = "resolved"
    gap.updated_at = _now()
    session.flush()
    return {"id": gap.id, "status": gap.status}


def get_gaps(
    session: Session,
    *,
    question_id: int | None = None,
    hypothesis_id: int | None = None,
) -> list[dict]:
    stmt = select(ResearchGap)
    if question_id is not None:
        stmt = stmt.where(ResearchGap.question_id == question_id)
    if hypothesis_id is not None:
        stmt = stmt.where(ResearchGap.hypothesis_id == hypothesis_id)
    rows = session.execute(stmt).scalars().all()
    return [
        {
            "id": g.id,
            "description": g.description,
            "gap_type": g.gap_type,
            "status": g.status,
            "question_id": g.question_id,
            "hypothesis_id": g.hypothesis_id,
        }
        for g in rows
    ]


# ---------------------------------------------------------------------------
# Question bundle
# ---------------------------------------------------------------------------

def get_question_bundle(session: Session, question_id: int) -> dict:
    question = session.get(ResearchQuestion, question_id)
    if question is None:
        return {}

    topic = None
    if question.topic_id is not None:
        topic = session.get(Topic, question.topic_id)

    hypotheses = session.execute(
        select(ResearchHypothesis).where(ResearchHypothesis.question_id == question_id)
    ).scalars().all()

    claims = get_approved_claims_for_topic(session, topic.id) if topic is not None else []
    gaps = get_gaps(session, question_id=question_id)

    return {
        "question": {
            "id": question.id,
            "question": question.question,
            "status": question.status,
            "topic_id": question.topic_id,
        },
        "topic": (
            {"id": topic.id, "name": topic.name, "description": topic.description}
            if topic is not None else None
        ),
        "hypotheses": [
            {"id": h.id, "title": h.title, "status": h.status}
            for h in hypotheses
        ],
        "claims": claims,
        "gaps": gaps,
    }
```

- [ ] **Step 4: Fix the broken note test**

The `test_get_evidence_links_source_type_for_note` test has a bad StudyNote constructor. Replace the broken lines in the test with:

```python
def test_get_evidence_links_source_type_for_note(session):
    hyp = _make_hypothesis(session)
    # SQLite doesn't enforce FK; use paper_id=1 as dummy anchor to satisfy CheckConstraint
    note = StudyNote(paper_id=1, concept_tag="LTP note", tagged_at=_now())
    session.add(note)
    session.flush()
    add_evidence_link(session, hyp.id, "supports", note_id=note.id)
    session.flush()

    links = get_evidence_links(session, hyp.id)
    assert links[0]["source_type"] == "note"
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_claim_store.py -v
```

Expected: all tests PASS.

```bash
uv run pytest tests/ -q
```

Expected: no new failures beyond the 9 pre-existing ones.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/db/claim_store.py tests/unit/test_claim_store.py
git commit -m "feat: add claim_store helper — claims, evidence links, research gaps, question bundle"
```

---

## Task 4: Research agent — 6 new tools

**Files:**
- Modify: `tests/unit/test_research_agent.py`
- Modify: `src/neurodb/agents/research_agent.py`

- [ ] **Step 1: Write failing tests in `tests/unit/test_research_agent.py`**

Append to the end of `tests/unit/test_research_agent.py`:

```python
# ---------------------------------------------------------------------------
# Phase 3 — 6 new claim/evidence/gap tools
# ---------------------------------------------------------------------------

def test_new_claim_tools_present_in_active_tools():
    names = {tool["name"] for tool in _agent()._get_active_tools()}
    assert "extract_claims" in names
    assert "update_claim_status" in names
    assert "add_evidence_link" in names
    assert "add_gap" in names
    assert "resolve_gap" in names
    assert "get_question_bundle" in names


def test_draft_hypothesis_evidence_is_optional():
    tool = next(
        t for t in _agent()._get_active_tools()
        if t["name"] == "draft_hypothesis"
    )
    assert "evidence" not in tool["input_schema"].get("required", [])


def test_system_prompt_mentions_get_question_bundle():
    prompt = _agent()._build_system_prompt()
    assert "get_question_bundle" in prompt


def test_update_claim_status_dispatch_updates_db():
    engine = _engine()
    agent = _agent(engine)
    with Session(engine) as session:
        paper = Paper(
            title="Test Paper", normalized_title="test paper",
            source_type="paper", topic_context="test", status="approved",
            queued_at="2026-01-01T00:00:00",
        )
        session.add(paper)
        session.flush()
        from neurodb.db.claim_store import create_claim
        claim = create_claim(session, paper.id, "A finding.", "finding")
        session.commit()
        claim_id = claim.id

    result = json.loads(agent._execute_tool_block(_block(
        "update_claim_status", {"claim_id": claim_id, "status": "approved"}
    )))
    assert result["status"] == "approved"


def test_add_gap_dispatch_persists_row():
    engine = _engine()
    agent = _agent(engine)
    with Session(engine) as session:
        q = ResearchQuestion(
            question="Does LTP matter?", topic_context="plasticity",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        session.add(q)
        session.commit()
        q_id = q.id

    result = json.loads(agent._execute_tool_block(_block(
        "add_gap",
        {
            "description": "No fMRI data for this topic.",
            "gap_type": "missing_dataset",
            "question_id": q_id,
        },
    )))
    assert "id" in result


def test_resolve_gap_dispatch_updates_status():
    engine = _engine()
    agent = _agent(engine)
    with Session(engine) as session:
        q = ResearchQuestion(
            question="LTP and memory?", topic_context="plasticity",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        session.add(q)
        session.flush()
        from neurodb.db.claim_store import add_gap
        gap = add_gap(session, "Missing data.", "missing_paper", question_id=q.id)
        session.commit()
        gap_id = gap.id

    result = json.loads(agent._execute_tool_block(_block(
        "resolve_gap", {"gap_id": gap_id}
    )))
    assert result["status"] == "resolved"


def test_get_question_bundle_dispatch_returns_bundle_shape():
    engine = _engine()
    agent = _agent(engine)
    with Session(engine) as session:
        q = ResearchQuestion(
            question="LTP question?", topic_context="plasticity",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        session.add(q)
        session.commit()
        q_id = q.id

    result = json.loads(agent._execute_tool_block(_block(
        "get_question_bundle", {"question_id": q_id}
    )))
    assert set(result.keys()) == {"question", "topic", "hypotheses", "claims", "gaps"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_research_agent.py -v -k "test_new_claim_tools or test_draft_hypothesis_evidence or test_system_prompt_mentions or test_update_claim or test_add_gap_dispatch or test_resolve_gap_dispatch or test_get_question_bundle_dispatch"
```

Expected: all new tests FAIL — tool names not found in active tools list, or dispatch not wired.

- [ ] **Step 3: Add 6 new tool definitions to `_RESEARCH_TOOLS` in `src/neurodb/agents/research_agent.py`**

After the closing `]` of `_RESEARCH_TOOLS` (currently ends after the `draft_hypothesis` entry on line ~165), replace the `]` with the extended list. The new entries go after `draft_hypothesis`:

```python
    {
        "name": "extract_claims",
        "description": (
            "Extract candidate claims from an approved paper using the paper's "
            "title, abstract, and summary. Stores each as a candidate claim for review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "paper_id": {
                    "type": "integer",
                    "description": "ID of the approved paper to extract claims from.",
                },
            },
            "required": ["paper_id"],
        },
    },
    {
        "name": "update_claim_status",
        "description": "Approve or reject a candidate claim.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "integer"},
                "status": {
                    "type": "string",
                    "description": "approved or rejected",
                },
            },
            "required": ["claim_id", "status"],
        },
    },
    {
        "name": "add_evidence_link",
        "description": (
            "Attach a structured evidence link to a hypothesis from a claim, paper, "
            "dataset packet, or study note."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hypothesis_id": {"type": "integer"},
                "link_type": {
                    "type": "string",
                    "description": "supports, contradicts, or contextualizes",
                },
                "source_type": {
                    "type": "string",
                    "description": "claim, paper, dataset, or note",
                },
                "source_id": {
                    "type": "integer",
                    "description": "ID of the source object (Claim.id, Paper.id, DatasetResearchPacket.id, or StudyNote.id)",
                },
            },
            "required": ["hypothesis_id", "link_type", "source_type", "source_id"],
        },
    },
    {
        "name": "add_gap",
        "description": "Record a named evidence gap for a research question or hypothesis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "gap_type": {
                    "type": "string",
                    "description": (
                        "missing_dataset, missing_paper, missing_evidence, "
                        "unsupported_claim, or other"
                    ),
                },
                "question_id": {"type": "integer"},
                "hypothesis_id": {"type": "integer"},
            },
            "required": ["description", "gap_type"],
        },
    },
    {
        "name": "resolve_gap",
        "description": "Mark an evidence gap as resolved.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gap_id": {"type": "integer"},
            },
            "required": ["gap_id"],
        },
    },
    {
        "name": "get_question_bundle",
        "description": (
            "Retrieve the full workspace context for a research question: "
            "topic, hypotheses, approved claims, and open gaps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question_id": {"type": "integer"},
            },
            "required": ["question_id"],
        },
    },
]
```

- [ ] **Step 4: Remove `"evidence"` from `draft_hypothesis` required list**

In `_RESEARCH_TOOLS`, find the `draft_hypothesis` entry. Change:

```python
"required": [
    "title",
    "mechanism",
    "evidence",
    "predictions",
    "datasets",
    "confounds",
    "limitations",
],
```

to:

```python
"required": [
    "title",
    "mechanism",
    "predictions",
    "confounds",
    "limitations",
],
```

- [ ] **Step 5: Append system prompt sentence in `_RESEARCH_SYSTEM_PROMPT`**

Change:

```python
_RESEARCH_SYSTEM_PROMPT = (
    "You are a neuroscience research partner for NeuroDb. ..."
    "Do not put raw tool JSON or debug traces in the final answer."
)
```

to (add the new sentence at the end, before the closing `"`):

```python
_RESEARCH_SYSTEM_PROMPT = (
    "You are a neuroscience research partner for NeuroDb. ..."
    "Do not put raw tool JSON or debug traces in the final answer. "
    "Before answering a research question, call get_question_bundle to retrieve the active "
    "topic, hypotheses, approved claims, and open gaps; use add_evidence_link to ground "
    "hypothesis drafts in local sources rather than free-text evidence; use add_gap when "
    "local evidence is insufficient to support a claim."
)
```

- [ ] **Step 6: Add 6 dispatch handlers in `_execute_tool_block`**

After the `if block.tool_name == "draft_hypothesis":` block and before the final `return execute_tool(...)` line, add:

```python
        if block.tool_name == "extract_claims":
            return json.dumps(self._execute_extract_claims(block.tool_input))
        if block.tool_name == "update_claim_status":
            from neurodb.db import get_session
            from neurodb.db.claim_store import update_claim_status as _update_claim_status
            with get_session(self._engine) as session:
                return json.dumps(_update_claim_status(
                    session,
                    block.tool_input["claim_id"],
                    block.tool_input["status"],
                ))
        if block.tool_name == "add_evidence_link":
            return json.dumps(self._execute_add_evidence_link(block.tool_input))
        if block.tool_name == "add_gap":
            from neurodb.db import get_session
            from neurodb.db.claim_store import add_gap as _add_gap
            with get_session(self._engine) as session:
                gap = _add_gap(
                    session,
                    block.tool_input["description"],
                    block.tool_input["gap_type"],
                    question_id=block.tool_input.get("question_id"),
                    hypothesis_id=block.tool_input.get("hypothesis_id"),
                )
                return json.dumps({"id": gap.id, "status": gap.status, "gap_type": gap.gap_type})
        if block.tool_name == "resolve_gap":
            from neurodb.db import get_session
            from neurodb.db.claim_store import resolve_gap as _resolve_gap
            with get_session(self._engine) as session:
                return json.dumps(_resolve_gap(session, block.tool_input["gap_id"]))
        if block.tool_name == "get_question_bundle":
            from neurodb.db import get_session
            from neurodb.db.claim_store import get_question_bundle as _get_question_bundle
            with get_session(self._engine) as session:
                return json.dumps(_get_question_bundle(session, block.tool_input["question_id"]))
```

- [ ] **Step 7: Add `_execute_extract_claims` and `_execute_add_evidence_link` helper methods**

Add these two methods to the `NeuroResearchAgent` class (after `_execute_search_literature`):

```python
    def _execute_extract_claims(self, inputs: dict) -> dict:
        from neurodb.db import get_session
        from neurodb.db.claim_store import create_claim, get_claims_for_paper
        from neurodb.schema import Paper

        paper_id = inputs["paper_id"]
        with get_session(self._engine) as session:
            paper = session.get(Paper, paper_id)
            if paper is None:
                return {"error": f"Paper {paper_id} not found"}
            if paper.status != "approved":
                return {"error": f"Paper {paper_id} is not approved (status={paper.status!r})"}

            parts = [f"Title: {paper.title}"]
            if paper.abstract:
                parts.append(f"Abstract: {paper.abstract}")
            if paper.summary:
                parts.append(f"Summary: {paper.summary}")
            context = "\n\n".join(parts)

            prompt = (
                "Extract distinct claims from this neuroscience paper. "
                "Return a JSON array of objects, each with 'text' (string) and "
                "'claim_type' (one of: finding, limitation, method, question).\n\n"
                f"{context}\n\nReturn only the JSON array."
            )
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            try:
                candidate_claims = json.loads(raw)
            except (json.JSONDecodeError, IndexError):
                return {"error": "Failed to parse claim extraction response", "raw": raw}

            created = []
            for item in candidate_claims:
                if not isinstance(item, dict) or "text" not in item or "claim_type" not in item:
                    continue
                try:
                    claim = create_claim(session, paper_id, item["text"], item["claim_type"])
                    created.append({"id": claim.id, "text": claim.text, "claim_type": claim.claim_type})
                except ValueError:
                    continue
            return {
                "paper_id": paper_id,
                "claims_created": len(created),
                "claims": created,
            }

    def _execute_add_evidence_link(self, inputs: dict) -> dict:
        from neurodb.db import get_session
        from neurodb.db.claim_store import add_evidence_link as _add_evidence_link

        source_type = inputs["source_type"]
        source_id = inputs["source_id"]
        source_kwargs = {
            "claim": {"claim_id": source_id},
            "paper": {"paper_id": source_id},
            "dataset": {"packet_id": source_id},
            "note": {"note_id": source_id},
        }
        if source_type not in source_kwargs:
            return {"error": f"Unknown source_type: {source_type!r}. Valid: claim, paper, dataset, note"}

        with get_session(self._engine) as session:
            link = _add_evidence_link(
                session,
                inputs["hypothesis_id"],
                inputs["link_type"],
                **source_kwargs[source_type],
            )
            return {
                "id": link.id,
                "hypothesis_id": link.hypothesis_id,
                "link_type": link.link_type,
                "source_type": source_type,
                "source_id": source_id,
            }
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_research_agent.py -v
```

Expected: all tests PASS including the new ones.

```bash
uv run pytest tests/ -q
```

Expected: no new failures beyond the 9 pre-existing ones.

- [ ] **Step 9: Commit**

```bash
git add src/neurodb/agents/research_agent.py tests/unit/test_research_agent.py
git commit -m "feat: add 6 research agent tools for claims, evidence links, and gaps; evidence optional on draft_hypothesis"
```

---

## Task 5: Integration test

**Files:**
- Create: `tests/integration/test_phase3_evidence_bundle.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_phase3_evidence_bundle.py`:

```python
"""End-to-end Phase 3 integration: claims, evidence links, research gaps, question bundle."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.db.claim_store import (
    add_evidence_link,
    add_gap,
    create_claim,
    get_evidence_links,
    get_gaps,
    get_question_bundle,
    resolve_gap,
    update_claim_status,
)
from neurodb.db.topic_store import get_or_create_topic, link_paper_topic
from neurodb.schema import (
    Base,
    DatasetIndex,
    DatasetResearchPacket,
    IngestRun,
    Paper,
    ResearchHypothesis,
    ResearchQuestion,
    StudyNote,
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


def test_question_linked_to_topic_returns_correct_bundle(engine):
    with Session(engine) as session:
        topic = get_or_create_topic(session, "synaptic plasticity")
        session.flush()

        question = ResearchQuestion(
            question="Does LTP drive long-term memory consolidation?",
            topic_context="synaptic plasticity",
            topic_id=topic.id,
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(question)
        session.commit()

        bundle = get_question_bundle(session, question.id)

    assert bundle["question"]["question"] == "Does LTP drive long-term memory consolidation?"
    assert bundle["topic"]["name"] == "synaptic plasticity"
    assert bundle["hypotheses"] == []
    assert bundle["claims"] == []
    assert bundle["gaps"] == []


def test_approved_claim_from_linked_paper_appears_in_bundle(engine):
    with Session(engine) as session:
        topic = get_or_create_topic(session, "hippocampal plasticity")
        session.flush()

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

        question = ResearchQuestion(
            question="How does LTP affect memory?",
            topic_context="hippocampal plasticity",
            topic_id=topic.id,
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(question)
        session.flush()

        claim = create_claim(session, paper.id, "LTP potentiates synaptic weight.", "finding")
        update_claim_status(session, claim.id, "approved")
        session.commit()

        bundle = get_question_bundle(session, question.id)

    assert any(c["text"] == "LTP potentiates synaptic weight." for c in bundle["claims"])


def test_evidence_links_of_all_source_types_stored_and_retrieved(engine):
    with Session(engine) as session:
        paper = Paper(
            title="Plasticity Review",
            normalized_title="plasticity review",
            source_type="paper",
            topic_context="plasticity",
            status="approved",
            queued_at=_now(),
        )
        session.add(paper)
        session.flush()

        question = ResearchQuestion(
            question="What drives plasticity?",
            topic_context="plasticity",
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(question)
        session.flush()

        hypothesis = ResearchHypothesis(
            question_id=question.id,
            title="Plasticity is NMDA-driven",
            mechanism="NMDA activation drives Ca2+ influx.",
            predictions_json="[]",
            limitations="Draft.",
            status="draft",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(hypothesis)
        session.flush()

        # Claim source
        claim = create_claim(session, paper.id, "NMDA drives LTP.", "finding")
        update_claim_status(session, claim.id, "approved")

        # Paper source
        link1 = add_evidence_link(session, hypothesis.id, "supports", claim_id=claim.id)
        link2 = add_evidence_link(session, hypothesis.id, "contextualizes", paper_id=paper.id)

        # Dataset source
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
        link3 = add_evidence_link(session, hypothesis.id, "contextualizes", packet_id=packet.id)

        # Note source
        note = StudyNote(paper_id=paper.id, concept_tag="NMDA review", tagged_at=_now())
        session.add(note)
        session.flush()
        link4 = add_evidence_link(session, hypothesis.id, "supports", note_id=note.id)

        session.commit()

        links = get_evidence_links(session, hypothesis.id)

    source_types = {lnk["source_type"] for lnk in links}
    assert source_types == {"claim", "paper", "dataset", "note"}


def test_gap_added_appears_in_bundle_and_resolves(engine):
    with Session(engine) as session:
        question = ResearchQuestion(
            question="What limits LTP research?",
            topic_context="plasticity",
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(question)
        session.flush()

        gap = add_gap(
            session,
            "No longitudinal human data available.",
            "missing_dataset",
            question_id=question.id,
        )
        session.commit()
        gap_id = gap.id
        q_id = question.id

    with Session(engine) as session:
        bundle = get_question_bundle(session, q_id)
        assert len(bundle["gaps"]) == 1
        assert bundle["gaps"][0]["status"] == "open"

        resolve_gap(session, gap_id)
        session.commit()

        updated_gaps = get_gaps(session, question_id=q_id)
        assert updated_gaps[0]["status"] == "resolved"


def test_hypothesis_with_no_evidence_links_returns_empty_list(engine):
    with Session(engine) as session:
        hypothesis = ResearchHypothesis(
            title="No evidence yet",
            mechanism="Unknown.",
            predictions_json="[]",
            limitations="Draft.",
            status="draft",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(hypothesis)
        session.commit()
        h_id = hypothesis.id

    with Session(engine) as session:
        assert get_evidence_links(session, h_id) == []
```

- [ ] **Step 2: Run integration test to verify it passes**

```bash
uv run pytest tests/integration/test_phase3_evidence_bundle.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 3: Run full suite**

```bash
uv run pytest tests/ -q
```

Expected: no new failures beyond the 9 pre-existing config-routing failures.

- [ ] **Step 4: Update `docs/projectStatus.md`**

In `docs/projectStatus.md`:
- Update the DB epoch row: increment test count to reflect new Phase 3 tests; add "Phase 3 (claims/evidence/gaps) implementation complete"
- Add the Phase 3 manual test plan to the reference table:
  `docs/testsPlans/manualTestPlan_db_phase3_claims_evidence.md`
- Update `Last updated` to today's date and `Active focus` to reflect Phase 3 manual verification pending

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_phase3_evidence_bundle.py docs/projectStatus.md
git commit -m "feat: Phase 3 integration test; update project status"
```
