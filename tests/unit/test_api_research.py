"""Tests for /api/research routes (Task 6 — UI-1 Backend API Shell)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.research import router


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


# ---------------------------------------------------------------------------
# Helpers to insert test data
# ---------------------------------------------------------------------------

def _insert_question(engine, question: str, status: str, topic_context: str = "ctx") -> None:
    from neurodb.schema import ResearchQuestion as ResearchQuestionORM
    from neurodb.db import get_session

    with get_session(engine) as session:
        session.add(ResearchQuestionORM(
            question=question,
            status=status,
            topic_context=topic_context,
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        ))


def _insert_hypothesis(engine, title: str, status: str) -> None:
    from neurodb.schema import ResearchHypothesis
    from neurodb.db import get_session

    with get_session(engine) as session:
        session.add(ResearchHypothesis(
            title=title,
            mechanism="test mechanism",
            evidence_json="[]",
            predictions_json="[]",
            datasets_json="[]",
            confounds_json="[]",
            limitations="none",
            status=status,
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        ))


# ---------------------------------------------------------------------------
# Metrics tests
# ---------------------------------------------------------------------------

def test_get_metrics_returns_count_fields():
    client, _ = _make_client()
    resp = client.get("/api/research/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "research_questions_count" in data
    assert "research_hypotheses_count" in data


def test_post_snapshot_persists_and_returns_snapshot_id():
    client, _ = _make_client()
    resp = client.post("/api/research/metrics/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "snapshot_id" in data
    assert data["snapshot_id"] is not None


# ---------------------------------------------------------------------------
# Research questions tests
# ---------------------------------------------------------------------------

def test_get_questions_returns_all():
    client, engine = _make_client()
    _insert_question(engine, "Question A", "open")
    _insert_question(engine, "Question B", "answered")
    resp = client.get("/api/research/questions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    titles = {q["question"] for q in data}
    assert "Question A" in titles
    assert "Question B" in titles


def test_get_questions_filters_by_status():
    client, engine = _make_client()
    _insert_question(engine, "Open Q", "open")
    _insert_question(engine, "Answered Q", "answered")
    resp = client.get("/api/research/questions?status=open")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["question"] == "Open Q"
    assert data[0]["status"] == "open"


# ---------------------------------------------------------------------------
# Hypotheses tests
# ---------------------------------------------------------------------------

def test_get_hypotheses_returns_all():
    client, engine = _make_client()
    _insert_hypothesis(engine, "Hypothesis Alpha", "draft")
    _insert_hypothesis(engine, "Hypothesis Beta", "reviewed")
    resp = client.get("/api/research/hypotheses")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    titles = {h["title"] for h in data}
    assert "Hypothesis Alpha" in titles
    assert "Hypothesis Beta" in titles


def test_get_hypotheses_filters_by_status():
    client, engine = _make_client()
    _insert_hypothesis(engine, "Draft H", "draft")
    _insert_hypothesis(engine, "Reviewed H", "reviewed")
    resp = client.get("/api/research/hypotheses?status=draft")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Draft H"
    assert data[0]["status"] == "draft"
