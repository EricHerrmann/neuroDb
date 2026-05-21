# Phase 5b — Evidence Lens, Dataset Honesty, and Retract Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface per-answer evidence provenance in chat, show dataset readiness honestly in the Datasets panel, and give users status-transition controls for evidence links, claims, gaps, and research questions.

**Architecture:** Backend-first: ORM schema update + DB migrations + new API endpoints, then three independent frontend features (Evidence Lens in MessageBubble, Dataset badge in DatasetsPanel, StatusChip-based retract UI in ResearchPanel). All four backend transitions use the same SQLAlchemy session pattern already established in the research routes. The Evidence Lens is purely frontend — it reads the `context_summary` SSE event already emitted by Phase 4.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy · DuckDB (prod) / SQLite (tests) · React 18 · TypeScript · Vite · @tanstack/react-query · vitest · @testing-library/react

---

## File Map

| File | Change |
|---|---|
| `src/neurodb/schema.py` | Add `status` field to `EvidenceLink` ORM model |
| `src/neurodb/db.py` | Add migrations 8 (evidence_links.status) + 9 (research_questions archived guard) |
| `src/neurodb/api/schemas/research.py` | Add `ClaimItem`, `ResearchGapItem`, `EvidenceLinkItem` schemas |
| `src/neurodb/api/schemas/datasets.py` | Add `usefulness_state` + `missing_context` to `DatasetItem` |
| `src/neurodb/api/routes/research.py` | Add 3 GET list endpoints + 6 status-transition POST endpoints |
| `src/neurodb/api/routes/datasets.py` | LEFT JOIN with `dataset_research_packets` in `GET /api/datasets` |
| `frontend/src/api/types.ts` | Add `ClaimItem`, `ResearchGapItem`, `EvidenceLinkItem`; update `DatasetItem`; add `evidenceSummary` to `Message` |
| `frontend/src/api/client.ts` | Add `api` methods for all new endpoints |
| `frontend/src/hooks/useChat.ts` | Handle `context_summary` SSE event; add `evidenceSummary` to `Message` |
| `frontend/src/components/MessageBubble.tsx` | Add `EvidenceLens` component rendering `<details>` from `evidenceSummary` |
| `frontend/src/pages/DatasetsPanel.tsx` | Add left-border + usefulness label to each result row |
| `frontend/src/components/StatusChip.tsx` | New — reusable clickable status chip with inline transition dropdown |
| `frontend/src/pages/ResearchPanel.tsx` | Add Claims accordion, Gaps accordion; StatusChips on question cards + evidence links |
| `tests/unit/test_api_research_p5b.py` | New — backend tests for all new endpoints |
| `tests/unit/test_api_datasets_p5b.py` | New — test usefulness_state in dataset response |
| `docs/testsPlans/manualTestPlan_phase5b_evidence_retract.md` | New — manual test plan (written before any code) |

---

## Task 1: Manual Test Plan

**Files:**
- Create: `docs/testsPlans/manualTestPlan_phase5b_evidence_retract.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Write the manual test plan**

Create `docs/testsPlans/manualTestPlan_phase5b_evidence_retract.md` with this content:

```markdown
# Manual Test Plan — Phase 5b: Evidence Lens, Dataset Honesty, and Retract Lifecycle

**Status:** Active — Phase 5b
**Date created:** 2026-05-21
**Spec:** `docs/superpowers/specs/2026-05-21-phase5b-evidence-lens-dataset-honesty-retract-design.md`

---

## Prerequisites

- [ ] Run automated tests: `uv run pytest tests/ -q`
  - Pass criterion: no new failures beyond those in `docs/testLog.md`
- [ ] Run frontend tests: `cd frontend && npm run test`
  - Pass criterion: all tests pass
- [ ] Start backend: `uv run uvicorn src.neurodb.api.app:app --reload --port 8000`
- [ ] Start frontend dev server: `cd frontend && npm run dev`
- [ ] Open browser to `http://localhost:5173`

---

## T1 — Evidence Lens: Contextual Mode

**Steps:**
1. Set agent mode to "Neuro Tutor", context mode to "Contextual".
2. Send: "What is long-term potentiation?"
3. Observe the assistant bubble after the response completes.
4. Locate the evidence `<details>` element below the response.
5. Click to expand it.

**Pass criteria:**
- A collapsed `<details>` element appears below the response text, labeled with mode and source counts
- Collapsed label format: `▸ Evidence: contextual · Np · Nn · Nc · Nd` (counts may be 0)
- Expanded body shows counts labeled clearly
- No evidence lens appears for Local DB or External DB turns

---

## T2 — Evidence Lens: Gap Warning

**Steps:**
1. Set agent mode to "Neuro Research", context mode to "Grounded".
2. Send: "What dataset evidence do I have for cortical remapping after stroke?"
3. Observe the collapsed evidence lens label.

**Pass criteria:**
- If `gaps > 0`, the collapsed label includes `· ⚠ N gap`
- Gap count is shown in amber in the expanded view

---

## T3 — Dataset Honesty: Usefulness Badge

**Steps:**
1. Open the Datasets panel.
2. Search for any keyword (try leaving it empty and pressing Search).
3. Observe dataset rows that have a research packet.

**Pass criteria:**
- Rows with `sparse` status show a red left border and "sparse — {gap note}" in the metadata column
- Rows with `partial` show an amber left border and "partial — {gap note}"
- Rows with `research_context_ready` or `analysis_ready` show a green left border and the state label
- Rows without a research packet render exactly as before (no border, no label)

---

## T4 — Research Questions: Archive Action

**Steps:**
1. Open the Research panel.
2. Locate a research question with status "open".
3. Click the status chip on that question.
4. Select "Archive" from the dropdown.

**Pass criteria:**
- Dropdown appears on chip click, showing "Archive"
- After clicking Archive, the question status updates to "archived" without a page reload
- The status chip color changes to muted/red

---

## T5 — Claims: Approve and Reject

**Steps:**
1. Open the Research panel.
2. Expand the Claims section.
3. Locate a claim with status "candidate".
4. Click its status chip and select "Approve".
5. Verify the status updates to "approved".
6. Click the chip again and select "Reject".
7. Verify the status updates to "rejected".

**Pass criteria:**
- Claims section is visible and lists claim cards
- Status chip transitions work without page reload
- Color coding: candidate = blue-grey, approved = green, rejected = red

---

## T6 — Gaps: Resolve and Archive

**Steps:**
1. Open the Research panel.
2. Expand the Gaps section.
3. Locate a gap with status "open".
4. Click its status chip and select "Resolve".
5. Verify the status updates to "resolved".

**Pass criteria:**
- Gaps section visible with gap cards
- Resolve transition works and status updates immediately

---

## T7 — Evidence Links: Retract

**Steps:**
1. Open the Research panel.
2. Find a hypothesis and click "Details" to expand it.
3. Locate an evidence link in the expanded view.
4. Click its status chip and select "Retract".

**Pass criteria:**
- Evidence link status chip visible on each link in the expanded hypothesis view
- Retract transitions the status to "retracted"
- Chip color changes to red/muted after retract

---

## Sign-Off

| Tester | Date | Result | Notes |
|---|---|---|---|
| | | | |
```

- [ ] **Step 2: Update `docs/projectStatus.md` to add the test plan reference**

In the Key References table, add after the Phase 5a manual test plan entry:
```
| `docs/testsPlans/manualTestPlan_phase5b_evidence_retract.md` | Phase 5b manual test plan — Evidence Lens, Dataset Honesty, Retract Lifecycle (T1-T7); active |
| `docs/superpowers/plans/2026-05-21-phase5b-evidence-lens-dataset-honesty-retract.md` | Phase 5b implementation plan |
```

- [ ] **Step 3: Commit**

```bash
git add docs/testsPlans/manualTestPlan_phase5b_evidence_retract.md docs/projectStatus.md docs/superpowers/plans/2026-05-21-phase5b-evidence-lens-dataset-honesty-retract.md
git commit -m "docs: add Phase 5b manual test plan and implementation plan"
```

---

## Task 2: ORM Update + DB Migrations

**Files:**
- Modify: `src/neurodb/schema.py` (EvidenceLink model, line ~495)
- Modify: `src/neurodb/db.py` (add migrations 8 and 9)
- Test: `tests/unit/test_migrations.py`

- [ ] **Step 1: Write failing tests for both migrations**

Add to `tests/unit/test_migrations.py` (append after existing tests):

```python
def test_migration_008_adds_evidence_links_status():
    """Migration 8 adds status column to evidence_links; idempotent on re-run."""
    from neurodb.migrations import apply_migrations

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create tables WITHOUT the status column by using the pre-migration schema
    # (We test idempotency by running the migration twice)
    Base.metadata.create_all(engine)

    # Import the actual migrations dict from db.py
    from neurodb.db import _MIGRATIONS

    apply_migrations(engine, {8: _MIGRATIONS[8]})
    apply_migrations(engine, {8: _MIGRATIONS[8]})  # idempotent — must not raise

    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT status FROM evidence_links LIMIT 1"
        ))
        # Column exists — no exception raised
        assert result is not None


def test_migration_009_research_questions_archived_guard_is_idempotent():
    """Migration 9 runs without error on a fresh DB (column already present)."""
    from neurodb.migrations import apply_migrations
    from neurodb.db import _MIGRATIONS

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    apply_migrations(engine, {9: _MIGRATIONS[9]})
    apply_migrations(engine, {9: _MIGRATIONS[9]})  # idempotent — must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_migrations.py::test_migration_008_adds_evidence_links_status tests/unit/test_migrations.py::test_migration_009_research_questions_archived_guard_is_idempotent -v
```
Expected: FAIL — `_MIGRATIONS` has no key 8 or 9.

- [ ] **Step 3: Add `status` to `EvidenceLink` in `schema.py`**

In `src/neurodb/schema.py`, add `status` as the last column before `created_at` in the `EvidenceLink` class:

```python
class EvidenceLink(Base):
    """Structured evidence link from a hypothesis to a claim, paper, dataset packet, or study note."""
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
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id"), nullable=True, index=True)
    paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id"), nullable=True, index=True)
    packet_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataset_research_packets.id"), nullable=True, index=True
    )
    note_id: Mapped[int | None] = mapped_column(ForeignKey("study_notes.id"), nullable=True, index=True)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

- [ ] **Step 4: Add migrations 8 and 9 to `src/neurodb/db.py`**

Add these two functions before `_MIGRATIONS`:

```python
def _migration_008_evidence_links_status(conn) -> None:
    """Add status column to evidence_links for retract lifecycle."""
    try:
        conn.execute(text("ALTER TABLE evidence_links ADD COLUMN status VARCHAR(16) DEFAULT 'active'"))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_evidence_links_status ON evidence_links (status)"
    ))


def _migration_009_research_questions_archived_guard(conn) -> None:
    """Guard migration: research_questions.status already exists; ensure index present."""
    try:
        conn.execute(text("ALTER TABLE research_questions ADD COLUMN status VARCHAR(32) DEFAULT 'open'"))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_research_questions_status ON research_questions (status)"
    ))
```

Update `_MIGRATIONS` to include them:

```python
_MIGRATIONS: dict[int, callable] = {
    1: _migration_001_study_note_unique,
    2: _migration_002_model_call_log,
    3: _migration_003_hypothesis_reviews,
    4: _migration_004_dataset_research_packets,
    5: _migration_005_study_notes_topic_id,
    6: _migration_006_study_notes_concept_paper_id,
    7: _migration_007_research_questions_topic_id,
    8: _migration_008_evidence_links_status,
    9: _migration_009_research_questions_archived_guard,
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_migrations.py::test_migration_008_adds_evidence_links_status tests/unit/test_migrations.py::test_migration_009_research_questions_archived_guard_is_idempotent -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/schema.py src/neurodb/db.py tests/unit/test_migrations.py
git commit -m "feat: add EvidenceLink.status field and DB migrations 8-9"
```

---

## Task 3: Backend Schemas for New Objects

**Files:**
- Modify: `src/neurodb/api/schemas/research.py`
- Modify: `src/neurodb/api/schemas/datasets.py`

No new test file needed here — schemas are validated through the route tests in Tasks 4–6.

- [ ] **Step 1: Add new schemas to `src/neurodb/api/schemas/research.py`**

Append to the end of the file:

```python
class ClaimItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    paper_id: int
    text: str
    claim_type: str
    status: str
    created_at: str
    updated_at: str


class ResearchGapItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    question_id: int | None = None
    hypothesis_id: int | None = None
    description: str
    gap_type: str
    status: str
    created_at: str
    updated_at: str


class EvidenceLinkItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    hypothesis_id: int
    claim_id: int | None = None
    paper_id: int | None = None
    packet_id: int | None = None
    note_id: int | None = None
    link_type: str
    status: str
    created_at: str
```

- [ ] **Step 2: Update `src/neurodb/api/schemas/datasets.py`**

Replace the file content:

```python
from __future__ import annotations

from pydantic import BaseModel


class DatasetItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source: str
    source_id: str
    title: str | None = None
    modality: str | None = None
    n_subjects: int | None = None
    usefulness_state: str | None = None
    missing_context: str | None = None
```

- [ ] **Step 3: Commit**

```bash
git add src/neurodb/api/schemas/research.py src/neurodb/api/schemas/datasets.py
git commit -m "feat: add ClaimItem, ResearchGapItem, EvidenceLinkItem schemas; dataset usefulness fields"
```

---

## Task 4: Backend — GET List Endpoints for Claims, Gaps, and Evidence Links

**Files:**
- Modify: `src/neurodb/api/routes/research.py`
- Test: `tests/unit/test_api_research_p5b.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_api_research_p5b.py`:

```python
"""Tests for Phase 5b research routes — list endpoints for claims, gaps, evidence links."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.db import get_session
from neurodb.schema import (
    Base,
    Claim,
    EvidenceLink,
    ResearchGap,
    ResearchHypothesis,
    ResearchQuestion,
    Paper,
)


def _make_client():
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


def _insert_paper(engine) -> int:
    with get_session(engine) as session:
        row = Paper(
            title="Test Paper",
            normalized_title="test paper",
            source_type="arxiv",
            topic_context="test",
            status="approved",
            queued_at="2026-01-01T00:00:00",
        )
        session.add(row)
        session.flush()
        return row.id


def _insert_claim(engine, paper_id: int, status: str = "candidate") -> int:
    with get_session(engine) as session:
        row = Claim(
            paper_id=paper_id,
            text="Synaptic density decreases post-stroke",
            claim_type="finding",
            status=status,
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        session.add(row)
        session.flush()
        return row.id


def _insert_hypothesis(engine) -> int:
    with get_session(engine) as session:
        row = ResearchHypothesis(
            title="Test Hypothesis",
            mechanism="test",
            predictions_json='["p1"]',
            limitations="none",
            status="draft",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        session.add(row)
        session.flush()
        return row.id


def _insert_gap(engine, hypothesis_id: int, status: str = "open") -> int:
    with get_session(engine) as session:
        row = ResearchGap(
            hypothesis_id=hypothesis_id,
            description="Missing dataset with lesion metadata",
            gap_type="missing_data",
            status=status,
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        session.add(row)
        session.flush()
        return row.id


def _insert_evidence_link(engine, hypothesis_id: int, paper_id: int, status: str = "active") -> int:
    with get_session(engine) as session:
        row = EvidenceLink(
            hypothesis_id=hypothesis_id,
            paper_id=paper_id,
            link_type="supports",
            status=status,
            created_at="2026-01-01T00:00:00",
        )
        session.add(row)
        session.flush()
        return row.id


# ---------------------------------------------------------------------------
# GET /api/research/claims
# ---------------------------------------------------------------------------

def test_get_claims_returns_empty_list():
    client, _ = _make_client()
    resp = client.get("/api/research/claims")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_claims_returns_claim_with_status():
    client, engine = _make_client()
    paper_id = _insert_paper(engine)
    claim_id = _insert_claim(engine, paper_id, status="candidate")
    resp = client.get("/api/research/claims")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == claim_id
    assert data[0]["status"] == "candidate"


# ---------------------------------------------------------------------------
# GET /api/research/gaps
# ---------------------------------------------------------------------------

def test_get_gaps_returns_empty_list():
    client, _ = _make_client()
    resp = client.get("/api/research/gaps")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_gaps_returns_gap():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)
    gap_id = _insert_gap(engine, hyp_id)
    resp = client.get("/api/research/gaps")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == gap_id
    assert data[0]["status"] == "open"


# ---------------------------------------------------------------------------
# GET /api/research/hypotheses/{id}/evidence-links
# ---------------------------------------------------------------------------

def test_get_evidence_links_returns_empty_list():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)
    resp = client.get(f"/api/research/hypotheses/{hyp_id}/evidence-links")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_evidence_links_returns_links_for_hypothesis():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)
    paper_id = _insert_paper(engine)
    link_id = _insert_evidence_link(engine, hyp_id, paper_id)
    resp = client.get(f"/api/research/hypotheses/{hyp_id}/evidence-links")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == link_id
    assert data[0]["status"] == "active"


def test_get_evidence_links_404_for_missing_hypothesis():
    client, _ = _make_client()
    resp = client.get("/api/research/hypotheses/9999/evidence-links")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_api_research_p5b.py::test_get_claims_returns_empty_list tests/unit/test_api_research_p5b.py::test_get_gaps_returns_empty_list tests/unit/test_api_research_p5b.py::test_get_evidence_links_returns_empty_list -v
```
Expected: FAIL — routes don't exist yet.

- [ ] **Step 3: Add GET endpoints to `src/neurodb/api/routes/research.py`**

Add these imports at the top of the routes file (after existing imports):

```python
from neurodb.api.schemas.research import (
    ClaimItem,
    EvidenceLinkItem,
    Hypothesis,
    HypothesisReviewItem,
    ResearchGapItem,
    ResearchQuestion,
)
from neurodb.schema import Claim, EvidenceLink, ResearchGap
```

(Replace the existing `from neurodb.api.schemas.research import ...` line with the expanded version above.)

Then add these three routes after the existing `get_questions` route:

```python
@router.get("/claims", response_model=list[ClaimItem])
def get_claims(
    engine: Engine = Depends(get_engine),
) -> list[ClaimItem]:
    """Return all claims."""
    with get_session(engine) as session:
        rows = session.query(Claim).order_by(Claim.created_at.desc()).all()
        return [ClaimItem.model_validate(row) for row in rows]


@router.get("/gaps", response_model=list[ResearchGapItem])
def get_gaps(
    engine: Engine = Depends(get_engine),
) -> list[ResearchGapItem]:
    """Return all research gaps."""
    with get_session(engine) as session:
        rows = session.query(ResearchGap).order_by(ResearchGap.created_at.desc()).all()
        return [ResearchGapItem.model_validate(row) for row in rows]


@router.get("/hypotheses/{hypothesis_id}/evidence-links", response_model=list[EvidenceLinkItem])
def get_evidence_links(
    hypothesis_id: int,
    engine: Engine = Depends(get_engine),
) -> list[EvidenceLinkItem]:
    """Return evidence links for a hypothesis."""
    with get_session(engine) as session:
        hypothesis = session.get(ResearchHypothesis, hypothesis_id)
        if hypothesis is None:
            raise HTTPException(
                status_code=404,
                detail=f"Hypothesis {hypothesis_id} not found",
            )
        rows = (
            session.query(EvidenceLink)
            .filter(EvidenceLink.hypothesis_id == hypothesis_id)
            .order_by(EvidenceLink.created_at.desc())
            .all()
        )
        return [EvidenceLinkItem.model_validate(row) for row in rows]
```

- [ ] **Step 4: Run all GET tests to verify they pass**

```bash
uv run pytest tests/unit/test_api_research_p5b.py::test_get_claims_returns_empty_list tests/unit/test_api_research_p5b.py::test_get_claims_returns_claim_with_status tests/unit/test_api_research_p5b.py::test_get_gaps_returns_empty_list tests/unit/test_api_research_p5b.py::test_get_gaps_returns_gap tests/unit/test_api_research_p5b.py::test_get_evidence_links_returns_empty_list tests/unit/test_api_research_p5b.py::test_get_evidence_links_returns_links_for_hypothesis tests/unit/test_api_research_p5b.py::test_get_evidence_links_404_for_missing_hypothesis -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/research.py src/neurodb/api/schemas/research.py tests/unit/test_api_research_p5b.py
git commit -m "feat: add GET endpoints for claims, gaps, and evidence links"
```

---

## Task 5: Backend — Status Transition Endpoints

**Files:**
- Modify: `src/neurodb/api/routes/research.py`
- Test: `tests/unit/test_api_research_p5b.py` (append)

- [ ] **Step 1: Write failing tests for all six transition endpoints**

Append to `tests/unit/test_api_research_p5b.py`:

```python
# ---------------------------------------------------------------------------
# POST /api/research/evidence-links/{id}/retract
# ---------------------------------------------------------------------------

def test_retract_evidence_link_sets_status():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)
    paper_id = _insert_paper(engine)
    link_id = _insert_evidence_link(engine, hyp_id, paper_id, status="active")
    resp = client.post(f"/api/research/evidence-links/{link_id}/retract")
    assert resp.status_code == 200
    assert resp.json()["status"] == "retracted"


def test_retract_evidence_link_404():
    client, _ = _make_client()
    resp = client.post("/api/research/evidence-links/9999/retract")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/research/questions/{id}/archive
# ---------------------------------------------------------------------------

def test_archive_question_sets_status():
    client, engine = _make_client()
    with get_session(engine) as session:
        q = ResearchQuestion(
            question="Does LTP correlate with stroke recovery?",
            topic_context="ctx",
            status="open",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        session.add(q)
        session.flush()
        question_id = q.id
    resp = client.post(f"/api/research/questions/{question_id}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_archive_question_404():
    client, _ = _make_client()
    resp = client.post("/api/research/questions/9999/archive")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/research/claims/{id}/approve and /reject
# ---------------------------------------------------------------------------

def test_approve_claim_sets_status():
    client, engine = _make_client()
    paper_id = _insert_paper(engine)
    claim_id = _insert_claim(engine, paper_id, status="candidate")
    resp = client.post(f"/api/research/claims/{claim_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_reject_claim_sets_status():
    client, engine = _make_client()
    paper_id = _insert_paper(engine)
    claim_id = _insert_claim(engine, paper_id, status="candidate")
    resp = client.post(f"/api/research/claims/{claim_id}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_approve_claim_404():
    client, _ = _make_client()
    resp = client.post("/api/research/claims/9999/approve")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/research/gaps/{id}/resolve and /archive
# ---------------------------------------------------------------------------

def test_resolve_gap_sets_status():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)
    gap_id = _insert_gap(engine, hyp_id, status="open")
    resp = client.post(f"/api/research/gaps/{gap_id}/resolve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


def test_archive_gap_sets_status():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)
    gap_id = _insert_gap(engine, hyp_id, status="open")
    resp = client.post(f"/api/research/gaps/{gap_id}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_resolve_gap_404():
    client, _ = _make_client()
    resp = client.post("/api/research/gaps/9999/resolve")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_api_research_p5b.py -k "retract or archive or approve or reject or resolve" -v
```
Expected: FAIL — endpoints don't exist.

- [ ] **Step 3: Add the six transition routes to `src/neurodb/api/routes/research.py`**

Add a helper at the bottom of the file (before the existing `_json_list` helper):

```python
def _update_status(engine: Engine, model_cls, item_id: int, status: str, schema_cls):
    """Generic status update helper. Returns 404 if item not found."""
    with get_session(engine) as session:
        row = session.get(model_cls, item_id)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"{model_cls.__name__} {item_id} not found",
            )
        row.status = status
        session.flush()
        return schema_cls.model_validate(row)
```

Then add these six routes after the evidence-links GET route:

```python
@router.post("/evidence-links/{link_id}/retract", response_model=EvidenceLinkItem)
def retract_evidence_link(
    link_id: int,
    engine: Engine = Depends(get_engine),
) -> EvidenceLinkItem:
    return _update_status(engine, EvidenceLink, link_id, "retracted", EvidenceLinkItem)


@router.post("/questions/{question_id}/archive", response_model=ResearchQuestion)
def archive_question(
    question_id: int,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestion:
    from neurodb.schema import ResearchQuestion as ResearchQuestionORM
    return _update_status(engine, ResearchQuestionORM, question_id, "archived", ResearchQuestion)


@router.post("/claims/{claim_id}/approve", response_model=ClaimItem)
def approve_claim(
    claim_id: int,
    engine: Engine = Depends(get_engine),
) -> ClaimItem:
    return _update_status(engine, Claim, claim_id, "approved", ClaimItem)


@router.post("/claims/{claim_id}/reject", response_model=ClaimItem)
def reject_claim(
    claim_id: int,
    engine: Engine = Depends(get_engine),
) -> ClaimItem:
    return _update_status(engine, Claim, claim_id, "rejected", ClaimItem)


@router.post("/gaps/{gap_id}/resolve", response_model=ResearchGapItem)
def resolve_gap(
    gap_id: int,
    engine: Engine = Depends(get_engine),
) -> ResearchGapItem:
    return _update_status(engine, ResearchGap, gap_id, "resolved", ResearchGapItem)


@router.post("/gaps/{gap_id}/archive", response_model=ResearchGapItem)
def archive_gap(
    gap_id: int,
    engine: Engine = Depends(get_engine),
) -> ResearchGapItem:
    return _update_status(engine, ResearchGap, gap_id, "archived", ResearchGapItem)
```

Also add `Claim`, `EvidenceLink`, `ResearchGap` to the existing schema import at the top:

```python
from neurodb.schema import Claim, EvidenceLink, HypothesisReview, ResearchGap, ResearchHypothesis
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
uv run pytest tests/unit/test_api_research_p5b.py -v
```
Expected: all PASS

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
uv run pytest tests/unit/test_api_research.py tests/unit/test_api_research_review.py tests/unit/test_api_research_p5b.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/api/routes/research.py tests/unit/test_api_research_p5b.py
git commit -m "feat: add retract/archive/approve/reject/resolve status transition endpoints"
```

---

## Task 6: Backend — Dataset Usefulness in GET /api/datasets

**Files:**
- Modify: `src/neurodb/api/routes/datasets.py`
- Test: `tests/unit/test_api_datasets_p5b.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_api_datasets_p5b.py`:

```python
"""Tests for Phase 5b: usefulness_state and missing_context in GET /api/datasets."""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.datasets import router
from neurodb.db import get_session
from neurodb.schema import Base, DatasetIndex, DatasetResearchPacket, IngestRun


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/datasets")
    return TestClient(app), engine


def _insert_dataset_with_packet(engine, source_id: str, usefulness: str, missing: list[str]) -> int:
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01", version="1", notes=None)
        session.add(run)
        session.flush()
        dataset = DatasetIndex(source="openneuro", source_id=source_id, run_id=run.id)
        session.add(dataset)
        session.flush()
        packet = DatasetResearchPacket(
            index_id=dataset.id,
            source="openneuro",
            source_id=source_id,
            usefulness_state=usefulness,
            supported_workflows_json="[]",
            unsupported_workflows_json="[]",
            missing_context_json=json.dumps(missing),
            provenance_json="{}",
            confidence_json="{}",
            harvested_at="2026-01-01T00:00:00",
            run_id=run.id,
        )
        session.add(packet)
        session.flush()
        return dataset.id


def _insert_dataset_without_packet(engine, source_id: str) -> int:
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01", version="1", notes=None)
        session.add(run)
        session.flush()
        dataset = DatasetIndex(source="openneuro", source_id=source_id, run_id=run.id)
        session.add(dataset)
        session.flush()
        return dataset.id


def test_dataset_with_packet_returns_usefulness_state():
    client, engine = _make_client()
    _insert_dataset_with_packet(engine, "ds001", "sparse", ["no linked paper"])
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["usefulness_state"] == "sparse"
    assert data[0]["missing_context"] == "no linked paper"


def test_dataset_without_packet_returns_null_fields():
    client, engine = _make_client()
    _insert_dataset_without_packet(engine, "ds002")
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["usefulness_state"] is None
    assert data[0]["missing_context"] is None


def test_dataset_with_research_ready_state():
    client, engine = _make_client()
    _insert_dataset_with_packet(engine, "ds003", "research_context_ready", [])
    resp = client.get("/api/datasets")
    data = resp.json()
    assert data[0]["usefulness_state"] == "research_context_ready"
    assert data[0]["missing_context"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_api_datasets_p5b.py -v
```
Expected: FAIL — `usefulness_state` not in response.

- [ ] **Step 3: Update `src/neurodb/api/routes/datasets.py`**

Replace the `get_datasets` function:

```python
@router.get("", response_model=list[DatasetItem])
def get_datasets(
    keyword: str | None = None,
    modality: str | None = None,
    engine: Engine = Depends(get_engine),
) -> list[DatasetItem]:
    with get_session(engine) as session:
        try:
            rows = search_datasets(
                session,
                keyword=keyword,
                modality=None if modality in {None, "", "all"} else modality,
            )
            # Enrich with usefulness data from research packets
            result = []
            for row in rows:
                item = dict(row)
                packet = session.execute(
                    select(DatasetResearchPacket).where(
                        DatasetResearchPacket.index_id == item["id"]
                    )
                ).scalar_one_or_none()
                if packet is not None:
                    import json as _json
                    missing_list = []
                    try:
                        missing_list = _json.loads(packet.missing_context_json or "[]")
                    except Exception:
                        pass
                    item["usefulness_state"] = packet.usefulness_state
                    item["missing_context"] = ", ".join(missing_list) if missing_list else ""
                else:
                    item["usefulness_state"] = None
                    item["missing_context"] = None
                result.append(DatasetItem(**item))
            return result
        except Exception:
            query = session.query(DatasetIndex)
            if keyword:
                query = query.filter(DatasetIndex.source_id.ilike(f"%{keyword}%"))
            rows = query.order_by(DatasetIndex.source, DatasetIndex.source_id).limit(200).all()
            items = []
            for row in rows:
                item = DatasetItem.model_validate(row)
                packet = session.execute(
                    select(DatasetResearchPacket).where(
                        DatasetResearchPacket.index_id == row.id
                    )
                ).scalar_one_or_none()
                if packet is not None:
                    import json as _json
                    missing_list = []
                    try:
                        missing_list = _json.loads(packet.missing_context_json or "[]")
                    except Exception:
                        pass
                    item.usefulness_state = packet.usefulness_state
                    item.missing_context = ", ".join(missing_list) if missing_list else ""
                else:
                    item.usefulness_state = None
                    item.missing_context = None
                items.append(item)
            if modality not in {None, "", "all"}:
                return []
            return items
```

Add the import for `DatasetResearchPacket` at the top:

```python
from neurodb.schema import DatasetIndex, DatasetResearchPacket, ImportQueue
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_api_datasets_p5b.py tests/unit/test_api_datasets.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/datasets.py tests/unit/test_api_datasets_p5b.py
git commit -m "feat: include usefulness_state and missing_context in GET /api/datasets"
```

---

## Task 7: Frontend — Types and API Client

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/hooks/useChat.ts` (Message interface only)

No test step here — types are validated through downstream component tests.

- [ ] **Step 1: Update `frontend/src/api/types.ts`**

Add to the `Message` interface (in `useChat.ts` — done in Task 8), and add new types to `types.ts`.

Add these type definitions to `frontend/src/api/types.ts` (append before the last closing of the file):

```ts
export interface EvidenceSummary {
  mode: string
  papers: number
  notes: number
  claims: number
  datasets: number
  gaps: number
}

export interface ClaimItem {
  id: number
  paper_id: number
  text: string
  claim_type: string
  status: string
  created_at: string
  updated_at: string
}

export interface ResearchGapItem {
  id: number
  question_id: number | null
  hypothesis_id: number | null
  description: string
  gap_type: string
  status: string
  created_at: string
  updated_at: string
}

export interface EvidenceLinkItem {
  id: number
  hypothesis_id: number
  claim_id: number | null
  paper_id: number | null
  packet_id: number | null
  note_id: number | null
  link_type: string
  status: string
  created_at: string
}
```

Also update the `DatasetItem` interface to add the two new fields:

```ts
export interface DatasetItem {
  id: number
  source: string
  source_id: string
  title: string | null
  modality: string | null
  n_subjects: number | null
  usefulness_state: string | null
  missing_context: string | null
}
```

- [ ] **Step 2: Add API methods to `frontend/src/api/client.ts`**

Add to the `api` object:

```ts
  getClaims: () => get<ClaimItem[]>('/api/research/claims'),
  getGaps: () => get<ResearchGapItem[]>('/api/research/gaps'),
  getEvidenceLinks: (hypothesisId: number) =>
    get<EvidenceLinkItem[]>(`/api/research/hypotheses/${hypothesisId}/evidence-links`),
  retractEvidenceLink: (id: number) =>
    post<EvidenceLinkItem>(`/api/research/evidence-links/${id}/retract`),
  archiveQuestion: (id: number) =>
    post<ResearchQuestion>(`/api/research/questions/${id}/archive`),
  approveClaim: (id: number) =>
    post<ClaimItem>(`/api/research/claims/${id}/approve`),
  rejectClaim: (id: number) =>
    post<ClaimItem>(`/api/research/claims/${id}/reject`),
  resolveGap: (id: number) =>
    post<ResearchGapItem>(`/api/research/gaps/${id}/resolve`),
  archiveGap: (id: number) =>
    post<ResearchGapItem>(`/api/research/gaps/${id}/archive`),
```

Add the import for new types at the top of `client.ts` (update the existing import line):

```ts
import type {
  ChatSession,
  ActiveContext,
  ClaimItem,
  CreateLearningSourceRequest,
  CreateStudyNoteRequest,
  DatasetItem,
  DeleteStudyNoteResponse,
  DuplicateCheckResponse,
  EvidenceLinkItem,
  EvidenceSummary,
  Hypothesis,
  HypothesisReviewItem,
  PaperItem,
  LearningSourceItem,
  ModelInfo,
  Preferences,
  ResearchGapItem,
  ResearchMetrics,
  ResearchQuestion,
  SqlResult,
  StudyNote,
  SuggestionsResponse,
  TaskResponse,
} from './types'
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "feat: add frontend types and API client methods for P5b endpoints"
```

---

## Task 8: Frontend — Evidence Lens

**Files:**
- Modify: `frontend/src/hooks/useChat.ts`
- Modify: `frontend/src/components/MessageBubble.tsx`
- Test: `frontend/src/hooks/useChat.test.ts` (if it exists, append; otherwise create)
- Test: `frontend/src/components/MessageBubble.test.tsx` (append)

- [ ] **Step 1: Write failing tests for useChat evidenceSummary**

Check if `frontend/src/hooks/useChat.test.ts` exists; if not, create it. Append (or create with):

```ts
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useChat } from './useChat'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('useChat evidenceSummary', () => {
  beforeEach(() => { vi.restoreAllMocks() })

  it('attaches evidenceSummary to message when context_summary event arrives', async () => {
    const sseLines = [
      'data: {"type":"context_summary","context_mode":"contextual","papers_count":3,"notes_count":2,"claims_count":1,"datasets_count":0,"gaps_count":1}',
      'data: {"type":"done","text":"Here is my answer."}',
    ].join('\n') + '\n'

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(sseLines, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    ))

    const { result } = renderHook(() => useChat('neuro_tutor'), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.sendMessage('What is LTP?')
    })

    const assistantMsg = result.current.messages.find(m => m.role === 'assistant')
    expect(assistantMsg?.evidenceSummary).toEqual({
      mode: 'contextual',
      papers: 3,
      notes: 2,
      claims: 1,
      datasets: 0,
      gaps: 1,
    })
  })

  it('evidenceSummary is null when no context_summary event', async () => {
    const sseLines = 'data: {"type":"done","text":"answer"}\n'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(sseLines, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    ))

    const { result } = renderHook(() => useChat('neuro_tutor'), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.sendMessage('test')
    })

    const assistantMsg = result.current.messages.find(m => m.role === 'assistant')
    expect(assistantMsg?.evidenceSummary ?? null).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test -- --reporter=verbose useChat
```
Expected: FAIL — `evidenceSummary` not on Message.

- [ ] **Step 3: Update `frontend/src/hooks/useChat.ts`**

Add `evidenceSummary` to the `Message` interface:

```ts
import type { EvidenceSummary } from '../api/types'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  error?: boolean
  activity?: ToolActivity[]
  evidenceSummary?: EvidenceSummary | null
}
```

In the SSE event loop, add a handler for `context_summary` after the `tool_result` handler:

```ts
} else if (event.type === 'context_summary') {
  setMessages(prev => {
    const next = [...prev]
    const last = { ...next[next.length - 1] }
    last.evidenceSummary = {
      mode: event.context_mode ?? 'unknown',
      papers: event.papers_count ?? 0,
      notes: event.notes_count ?? 0,
      claims: event.claims_count ?? 0,
      datasets: event.datasets_count ?? 0,
      gaps: event.gaps_count ?? 0,
    }
    next[next.length - 1] = last
    return next
  })
}
```

Also extend the SSE event type annotation at the top of the while loop to include the new fields:

```ts
const event = JSON.parse(payload) as {
  type: string
  text?: string
  tool_name?: string
  tool_input?: unknown
  result?: string
  context_mode?: string
  papers_count?: number
  notes_count?: number
  claims_count?: number
  datasets_count?: number
  gaps_count?: number
}
```

- [ ] **Step 4: Run useChat tests to verify they pass**

```bash
cd frontend && npm run test -- --reporter=verbose useChat
```
Expected: PASS

- [ ] **Step 5: Write failing tests for MessageBubble EvidenceLens**

Append to `frontend/src/components/MessageBubble.test.tsx`:

```tsx
describe('EvidenceLens', () => {
  it('renders evidence details when evidenceSummary present', () => {
    const msg: Message = {
      role: 'assistant',
      content: 'test response',
      evidenceSummary: { mode: 'contextual', papers: 3, notes: 2, claims: 1, datasets: 0, gaps: 0 },
    }
    render(<MessageBubble message={msg} />)
    expect(screen.getByText(/Evidence:/)).toBeTruthy()
    expect(screen.getByText(/3p/)).toBeTruthy()
  })

  it('shows gap warning when gaps > 0', () => {
    const msg: Message = {
      role: 'assistant',
      content: 'test',
      evidenceSummary: { mode: 'grounded', papers: 1, notes: 0, claims: 0, datasets: 0, gaps: 2 },
    }
    render(<MessageBubble message={msg} />)
    expect(screen.getByText(/⚠ 2 gap/)).toBeTruthy()
  })

  it('does not render evidence details when evidenceSummary absent', () => {
    const msg: Message = { role: 'assistant', content: 'test' }
    render(<MessageBubble message={msg} />)
    expect(screen.queryByText(/Evidence:/)).toBeNull()
  })
})
```

- [ ] **Step 6: Run MessageBubble tests to verify they fail**

```bash
cd frontend && npm run test -- --reporter=verbose MessageBubble
```
Expected: FAIL — no `EvidenceLens` component.

- [ ] **Step 7: Add `EvidenceLens` to `frontend/src/components/MessageBubble.tsx`**

Add this function before the `ActivityLog` function:

```tsx
function EvidenceLens({ message }: { message: Message }) {
  const s = message.evidenceSummary
  if (!s) return null
  const summary = `Evidence: ${s.mode} · ${s.papers}p · ${s.notes}n · ${s.claims}c · ${s.datasets}d`
  const gapWarning = s.gaps > 0 ? ` · ⚠ ${s.gaps} gap` : ''
  return (
    <details style={{ marginTop: 6, fontSize: 11, color: '#475569' }}>
      <summary style={{ cursor: 'pointer' }}>{summary}{gapWarning}</summary>
      <div style={{ marginTop: 4, paddingLeft: 8, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span>Mode: {s.mode}</span>
        <span>Papers: {s.papers} · Notes: {s.notes} · Claims: {s.claims} · Datasets: {s.datasets}</span>
        {s.gaps > 0 && (
          <span style={{ color: '#d97706' }}>Gaps: {s.gaps}</span>
        )}
      </div>
    </details>
  )
}
```

In the `MessageBubble` component, render `<EvidenceLens>` after `<ActivityLog>`:

```tsx
<MarkdownContent text={message.content} />
{message.streaming && <span style={{ opacity: 0.5 }}>▋</span>}
<ActivityLog message={message} />
<EvidenceLens message={message} />
```

- [ ] **Step 8: Run all MessageBubble tests to verify they pass**

```bash
cd frontend && npm run test -- --reporter=verbose MessageBubble
```
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add frontend/src/hooks/useChat.ts frontend/src/components/MessageBubble.tsx
git commit -m "feat: add Evidence Lens to MessageBubble from context_summary SSE events"
```

---

## Task 9: Frontend — Dataset Honesty Badge

**Files:**
- Modify: `frontend/src/pages/DatasetsPanel.tsx`
- Test: append to `frontend/src/pages/DatasetsPanel.test.tsx` (create if not exists)

- [ ] **Step 1: Write failing tests**

Check for `frontend/src/pages/DatasetsPanel.test.tsx`; create if missing. Append:

```tsx
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DatasetsPanel from './DatasetsPanel'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('DatasetsPanel usefulness badge', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('shows sparse label and red border for sparse dataset', async () => {
    const mockDataset = {
      id: 1, source: 'openneuro', source_id: 'ds001',
      title: 'Stroke fMRI', modality: 'fMRI', n_subjects: 42,
      usefulness_state: 'sparse', missing_context: 'no linked paper',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify([mockDataset]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))
    render(<DatasetsPanel />, { wrapper: makeWrapper() })
    // Trigger search
    const searchBtn = screen.getByRole('button', { name: 'Search' })
    searchBtn.click()
    await waitFor(() => {
      expect(screen.getByText(/sparse/)).toBeTruthy()
      expect(screen.getByText(/no linked paper/)).toBeTruthy()
    })
  })

  it('shows no badge for dataset without usefulness_state', async () => {
    const mockDataset = {
      id: 2, source: 'openneuro', source_id: 'ds002',
      title: 'Motor fMRI', modality: 'fMRI', n_subjects: 10,
      usefulness_state: null, missing_context: null,
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify([mockDataset]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))
    render(<DatasetsPanel />, { wrapper: makeWrapper() })
    screen.getByRole('button', { name: 'Search' }).click()
    await waitFor(() => {
      expect(screen.queryByText(/sparse/)).toBeNull()
      expect(screen.queryByText(/partial/)).toBeNull()
    })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test -- --reporter=verbose DatasetsPanel
```
Expected: FAIL — no badge rendering.

- [ ] **Step 3: Update `frontend/src/pages/DatasetsPanel.tsx`**

Add a helper function before the component:

```tsx
function usefulnessBorderColor(state: string | null | undefined): string {
  if (state === 'sparse') return '#ef4444'
  if (state === 'partial') return '#f59e0b'
  if (state === 'research_context_ready' || state === 'analysis_ready') return '#22c55e'
  return 'transparent'
}

function usefulnessLabel(state: string | null | undefined, missing: string | null | undefined): string | null {
  if (!state) return null
  if (state === 'sparse' || state === 'partial') {
    return missing ? `${state} — ${missing}` : state
  }
  if (state === 'research_context_ready') return 'research context ready'
  if (state === 'analysis_ready') return 'analysis ready'
  return null
}
```

In the table body, update the metadata `<td>` for each row:

```tsx
<td style={{ padding: '4px 8px', color: '#475569', borderLeft: `3px solid ${usefulnessBorderColor(row.usefulness_state)}` }}>
  <span>{row.modality || 'unknown modality'}</span>
  <span style={{ marginLeft: 8 }}>{row.n_subjects ?? '-'} subjects</span>
  {usefulnessLabel(row.usefulness_state, row.missing_context) && (
    <span style={{ marginLeft: 8, fontSize: 10, color: usefulnessBorderColor(row.usefulness_state) }}>
      {usefulnessLabel(row.usefulness_state, row.missing_context)}
    </span>
  )}
</td>
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npm run test -- --reporter=verbose DatasetsPanel
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/DatasetsPanel.tsx
git commit -m "feat: add dataset usefulness badge to Datasets panel"
```

---

## Task 10: Frontend — StatusChip Component

**Files:**
- Create: `frontend/src/components/StatusChip.tsx`
- Test: `frontend/src/components/StatusChip.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/StatusChip.test.tsx`:

```tsx
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import StatusChip from './StatusChip'

describe('StatusChip', () => {
  it('renders current status', () => {
    render(
      <StatusChip
        status="candidate"
        transitions={[{ label: 'Approve', onSelect: vi.fn() }]}
      />
    )
    expect(screen.getByText('candidate')).toBeTruthy()
  })

  it('opens dropdown on click', () => {
    render(
      <StatusChip
        status="candidate"
        transitions={[
          { label: 'Approve', onSelect: vi.fn() },
          { label: 'Reject', onSelect: vi.fn() },
        ]}
      />
    )
    fireEvent.click(screen.getByText('candidate'))
    expect(screen.getByText('Approve')).toBeTruthy()
    expect(screen.getByText('Reject')).toBeTruthy()
  })

  it('calls onSelect and closes dropdown when transition clicked', () => {
    const onApprove = vi.fn()
    render(
      <StatusChip
        status="candidate"
        transitions={[{ label: 'Approve', onSelect: onApprove }]}
      />
    )
    fireEvent.click(screen.getByText('candidate'))
    fireEvent.click(screen.getByText('Approve'))
    expect(onApprove).toHaveBeenCalledOnce()
    expect(screen.queryByText('Approve')).toBeNull()
  })

  it('shows disabled state when isPending', () => {
    render(
      <StatusChip
        status="candidate"
        transitions={[{ label: 'Approve', onSelect: vi.fn() }]}
        isPending={true}
      />
    )
    const chip = screen.getByText('candidate').closest('button') as HTMLButtonElement
    expect(chip.disabled).toBe(true)
  })

  it('applies green color for approved status', () => {
    render(
      <StatusChip status="approved" transitions={[]} />
    )
    const chip = screen.getByText('approved').closest('button') as HTMLButtonElement
    expect(chip.style.background).toContain('14532d')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test -- --reporter=verbose StatusChip
```
Expected: FAIL — component doesn't exist.

- [ ] **Step 3: Create `frontend/src/components/StatusChip.tsx`**

```tsx
import { useState } from 'react'

interface Transition {
  label: string
  onSelect: () => void
}

interface StatusChipProps {
  status: string
  transitions: Transition[]
  isPending?: boolean
}

function chipColors(status: string): { background: string; color: string; border: string } {
  if (status === 'approved' || status === 'resolved' || status === 'active') {
    return { background: '#14532d', color: '#86efac', border: '#166534' }
  }
  if (status === 'rejected' || status === 'retracted' || status === 'archived') {
    return { background: '#7f1d1d', color: '#fca5a5', border: '#991b1b' }
  }
  return { background: '#1e293b', color: '#94a3b8', border: '#334155' }
}

export default function StatusChip({ status, transitions, isPending }: StatusChipProps) {
  const [open, setOpen] = useState(false)
  const { background, color, border } = chipColors(status)

  if (transitions.length === 0) {
    return (
      <span style={{
        background, color,
        border: `1px solid ${border}`,
        fontSize: 9, padding: '2px 7px', borderRadius: 10,
      }}>
        {status}
      </span>
    )
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        disabled={isPending}
        onClick={() => setOpen(v => !v)}
        style={{
          background, color,
          border: `1px solid ${border}`,
          fontSize: 9, padding: '2px 7px', borderRadius: 10,
          cursor: isPending ? 'not-allowed' : 'pointer',
          opacity: isPending ? 0.6 : 1,
        }}
      >
        {status} {transitions.length > 0 ? '▾' : ''}
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, zIndex: 10,
          background: '#0f172a', border: '1px solid #334155', borderRadius: 4,
          padding: 4, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 80,
        }}>
          {transitions.map(t => (
            <button
              key={t.label}
              type="button"
              onClick={() => { t.onSelect(); setOpen(false) }}
              style={{
                background: 'none', border: 'none', textAlign: 'left',
                padding: '3px 8px', fontSize: 10, color: '#94a3b8', cursor: 'pointer',
                borderRadius: 3,
              }}
              onMouseEnter={e => { (e.target as HTMLElement).style.background = '#1e293b' }}
              onMouseLeave={e => { (e.target as HTMLElement).style.background = 'none' }}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npm run test -- --reporter=verbose StatusChip
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StatusChip.tsx frontend/src/components/StatusChip.test.tsx
git commit -m "feat: add reusable StatusChip component with inline transition dropdown"
```

---

## Task 11: Frontend — Research Panel Retract UI

**Files:**
- Modify: `frontend/src/pages/ResearchPanel.tsx`
- Test: `frontend/src/pages/ResearchPanel.test.tsx` (append)

- [ ] **Step 1: Write failing tests**

Append to `frontend/src/pages/ResearchPanel.test.tsx` (create if not present):

```tsx
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ResearchPanel from './ResearchPanel'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('ResearchPanel retract UI', () => {
  beforeEach(() => { vi.restoreAllMocks() })

  it('renders Archive status chip on research question cards', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (path.includes('/api/research/questions')) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: 1, question: 'Does LTP correlate with recovery?', status: 'open', created_at: '2026-01-01T00:00:00' }
        ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }))
    render(<ResearchPanel />, { wrapper: makeWrapper() })
    await waitFor(() => {
      expect(screen.getByText('Does LTP correlate with recovery?')).toBeTruthy()
      expect(screen.getByText('open')).toBeTruthy()
    })
  })

  it('renders Claims section', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (path.includes('/api/research/claims')) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: 1, paper_id: 1, text: 'Synaptic density decreases', claim_type: 'finding', status: 'candidate', created_at: '2026-01-01', updated_at: '2026-01-01' }
        ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }))
    render(<ResearchPanel />, { wrapper: makeWrapper() })
    await waitFor(() => {
      expect(screen.getByText(/Claims/)).toBeTruthy()
    })
  })

  it('renders Gaps section', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((path: string) => {
      if (path.includes('/api/research/gaps')) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: 1, hypothesis_id: 1, question_id: null, description: 'Missing lesion data', gap_type: 'missing_data', status: 'open', created_at: '2026-01-01', updated_at: '2026-01-01' }
        ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }))
    render(<ResearchPanel />, { wrapper: makeWrapper() })
    await waitFor(() => {
      expect(screen.getByText(/Gaps/)).toBeTruthy()
    })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test -- --reporter=verbose ResearchPanel
```
Expected: FAIL — Claims/Gaps sections not present.

- [ ] **Step 3: Update `frontend/src/pages/ResearchPanel.tsx`**

Add imports at the top:

```tsx
import StatusChip from '../components/StatusChip'
import type { ClaimItem, ResearchGapItem, EvidenceLinkItem } from '../api/types'
```

Replace the inline research question rendering (the `.map(question => ...)` block inside the Research Questions section) with:

```tsx
{questions.map(question => (
  <div key={question.id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
    <div>
      <div style={{ fontSize: 13 }}>{question.question}</div>
      <div style={{ fontSize: 11, color: '#94a3b8' }}>{question.created_at?.slice(0, 10)}</div>
    </div>
    <QuestionStatusChip question={question} />
  </div>
))}
```

Add the `QuestionStatusChip` component before `ResearchPanel`:

```tsx
function QuestionStatusChip({ question }: { question: { id: number; status: string } }) {
  const queryClient = useQueryClient()
  const archive = useMutation({
    mutationFn: () => api.archiveQuestion(question.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-questions'] }),
  })
  const transitions = question.status !== 'archived'
    ? [{ label: 'Archive', onSelect: () => archive.mutate() }]
    : []
  return <StatusChip status={question.status} transitions={transitions} isPending={archive.isPending} />
}
```

Add Claims section after the Research Questions section (before the hypotheses `<hr>`):

```tsx
<hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

<ClaimsSection />

<hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

<GapsSection />
```

Add the `ClaimsSection` component:

```tsx
function ClaimsSection() {
  const queryClient = useQueryClient()
  const { data: claims = [], isLoading } = useQuery({
    queryKey: ['research-claims'],
    queryFn: api.getClaims,
  })

  function ClaimChip({ claim }: { claim: ClaimItem }) {
    const approve = useMutation({
      mutationFn: () => api.approveClaim(claim.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-claims'] }),
    })
    const reject = useMutation({
      mutationFn: () => api.rejectClaim(claim.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-claims'] }),
    })
    const transitions = []
    if (claim.status === 'candidate' || claim.status === 'rejected') {
      transitions.push({ label: 'Approve', onSelect: () => approve.mutate() })
    }
    if (claim.status === 'candidate' || claim.status === 'approved') {
      transitions.push({ label: 'Reject', onSelect: () => reject.mutate() })
    }
    return (
      <StatusChip
        status={claim.status}
        transitions={transitions}
        isPending={approve.isPending || reject.isPending}
      />
    )
  }

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>
        Claims ({claims.length})
      </div>
      {isLoading ? (
        <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
      ) : claims.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 12 }}>No claims yet.</p>
      ) : claims.map(claim => (
        <div key={claim.id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <div>
            <div style={{ fontSize: 12, color: '#334155' }}>{claim.text}</div>
            <div style={{ fontSize: 10, color: '#94a3b8' }}>{claim.claim_type} · {claim.created_at?.slice(0, 10)}</div>
          </div>
          <ClaimChip claim={claim} />
        </div>
      ))}
    </div>
  )
}
```

Add the `GapsSection` component:

```tsx
function GapsSection() {
  const queryClient = useQueryClient()
  const { data: gaps = [], isLoading } = useQuery({
    queryKey: ['research-gaps'],
    queryFn: api.getGaps,
  })

  function GapChip({ gap }: { gap: ResearchGapItem }) {
    const resolve = useMutation({
      mutationFn: () => api.resolveGap(gap.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-gaps'] }),
    })
    const archive = useMutation({
      mutationFn: () => api.archiveGap(gap.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-gaps'] }),
    })
    const transitions = []
    if (gap.status === 'open') {
      transitions.push({ label: 'Resolve', onSelect: () => resolve.mutate() })
    }
    if (gap.status !== 'archived') {
      transitions.push({ label: 'Archive', onSelect: () => archive.mutate() })
    }
    return (
      <StatusChip
        status={gap.status}
        transitions={transitions}
        isPending={resolve.isPending || archive.isPending}
      />
    )
  }

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>
        Gaps ({gaps.length})
      </div>
      {isLoading ? (
        <span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span>
      ) : gaps.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 12 }}>No gaps yet.</p>
      ) : gaps.map(gap => (
        <div key={gap.id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <div>
            <div style={{ fontSize: 12, color: '#334155' }}>{gap.description}</div>
            <div style={{ fontSize: 10, color: '#94a3b8' }}>{gap.gap_type} · {gap.created_at?.slice(0, 10)}</div>
          </div>
          <GapChip gap={gap} />
        </div>
      ))}
    </div>
  )
}
```

Update `HypothesisDetails` to show evidence links with retract chip. Replace the function:

```tsx
function HypothesisDetails({ hypothesis }: { hypothesis: Hypothesis }) {
  const queryClient = useQueryClient()
  const { data: evidenceLinks = [] } = useQuery({
    queryKey: ['evidence-links', hypothesis.id],
    queryFn: () => api.getEvidenceLinks(hypothesis.id),
  })

  function LinkChip({ link }: { link: EvidenceLinkItem }) {
    const retract = useMutation({
      mutationFn: () => api.retractEvidenceLink(link.id),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['evidence-links', hypothesis.id] }),
    })
    const transitions = link.status === 'active'
      ? [{ label: 'Retract', onSelect: () => retract.mutate() }]
      : []
    return <StatusChip status={link.status} transitions={transitions} isPending={retract.isPending} />
  }

  return (
    <div style={{ marginTop: 8, padding: 8, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6 }}>
      {hypothesis.mechanism && (
        <div style={{ fontSize: 12, color: '#334155', marginBottom: 6 }}>
          <strong>Mechanism:</strong> {hypothesis.mechanism}
        </div>
      )}
      <ReviewList label="Evidence" values={hypothesis.evidence_json} />
      <ReviewList label="Predictions" values={hypothesis.predictions_json} />
      <ReviewList label="Relevant datasets" values={hypothesis.datasets_json} />
      <ReviewList label="Confounds" values={hypothesis.confounds_json} />
      {hypothesis.limitations && (
        <div style={{ marginTop: 6, fontSize: 11, color: '#334155' }}>
          <strong>Limitations:</strong> {hypothesis.limitations}
        </div>
      )}
      {evidenceLinks.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 4 }}>Evidence Links</div>
          {evidenceLinks.map(link => (
            <div key={link.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '3px 0', fontSize: 11, color: '#334155' }}>
              <span>{link.link_type} · paper:{link.paper_id ?? link.claim_id ?? link.packet_id ?? link.note_id}</span>
              <LinkChip link={link} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run ResearchPanel tests to verify they pass**

```bash
cd frontend && npm run test -- --reporter=verbose ResearchPanel
```
Expected: PASS

- [ ] **Step 5: Run full frontend test suite**

```bash
cd frontend && npm run test
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ResearchPanel.tsx frontend/src/pages/ResearchPanel.test.tsx
git commit -m "feat: add Claims/Gaps accordions and status chips to Research panel"
```

---

## Task 12: Build, Docs Sync, and Final Commit

**Files:**
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Run full backend test suite**

```bash
uv run pytest tests/ -q
```
Expected: no new failures beyond those already in `docs/testLog.md`.

- [ ] **Step 2: Build the frontend**

```bash
cd frontend && npm run build
```
Expected: build completes with no errors.

- [ ] **Step 3: Update `docs/projectStatus.md`**

Update the UI epoch row to reflect P5b implementation complete:

```
| UI | `src/neurodb/ui/`, `src/neurodb/api/`, `frontend/` | ... Phase 5b implementation complete; manual verification pending | Phase 5b manual verification; UI-5 common manual verification |
```

Update active focus:
```
**Active focus:** Phase 5b — Evidence Lens, Dataset Honesty, Retract Lifecycle; implementation complete, manual verification pending
**Next:** Phase 5b manual verification; UI-5 common manual verification
```

- [ ] **Step 4: Final commit**

```bash
git add docs/projectStatus.md
git commit -m "docs: sync project status after Phase 5b implementation complete"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Migration 8 — EvidenceLink.status | Task 2 |
| Migration 9 — ResearchQuestion archived guard | Task 2 |
| POST /api/research/evidence-links/{id}/retract | Task 5 |
| POST /api/research/questions/{id}/archive | Task 5 |
| POST /api/research/claims/{id}/approve + /reject | Task 5 |
| POST /api/research/gaps/{id}/resolve + /archive | Task 5 |
| GET /api/datasets includes usefulness_state + missing_context | Task 6 |
| Message.evidenceSummary from context_summary SSE | Task 8 |
| EvidenceLens `<details>` in MessageBubble | Task 8 |
| Dataset usefulness badge (left-border + label) in DatasetsPanel | Task 9 |
| StatusChip component | Task 10 |
| Claims accordion + status chips in ResearchPanel | Task 11 |
| Gaps accordion + status chips in ResearchPanel | Task 11 |
| Evidence link retract chip in HypothesisDetails | Task 11 |
| Question status chip in ResearchPanel | Task 11 |
| Manual test plan written before implementation code | Task 1 |

**Gaps found:** None — all spec requirements are covered.

**Type consistency check:** `EvidenceSummary` defined in `types.ts` (Task 7), imported in `useChat.ts` (Task 8). `ClaimItem`, `ResearchGapItem`, `EvidenceLinkItem` defined in `types.ts` (Task 7), used in `ResearchPanel.tsx` (Task 11). `DatasetItem` updated in Task 7, rendered in Task 9. `_update_status` helper defined in Task 5 and used by all six transition routes. All consistent.
