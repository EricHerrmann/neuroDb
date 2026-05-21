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
