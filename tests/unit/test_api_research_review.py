"""Tests for POST /api/research/hypotheses/{id}/review route."""
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.db import get_session
from neurodb.schema import Base, HypothesisReview, ResearchHypothesis


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.state.tasks = {}
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


def _insert_hypothesis(engine) -> int:
    with get_session(engine) as session:
        hyp = ResearchHypothesis(
            title="LTP Hypothesis",
            mechanism="Calcium influx",
            evidence_json="[]",
            predictions_json="[]",
            datasets_json="[]",
            confounds_json="[]",
            limitations="Preliminary",
            status="draft",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        session.add(hyp)
        session.flush()
        return hyp.id


def test_review_hypothesis_returns_task_id():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)

    with patch("neurodb.api.routes.research.threading.Thread") as mock_thread:
        mock_thread.return_value.start = lambda: None
        resp = client.post(f"/api/research/hypotheses/{hyp_id}/review")

    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert isinstance(data["task_id"], str)


def test_review_hypothesis_task_is_in_store():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)

    with patch("neurodb.api.routes.research.threading.Thread") as mock_thread:
        mock_thread.return_value.start = lambda: None
        resp = client.post(f"/api/research/hypotheses/{hyp_id}/review")

    task_id = resp.json()["task_id"]
    record = client.app.state.tasks[task_id]
    assert record.status == "running"
    assert record.result is None


def test_review_hypothesis_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/research/hypotheses/9999/review")
    assert resp.status_code == 404


def _insert_review(engine, hypothesis_id: int, *, status: str = "pending") -> None:
    with get_session(engine) as session:
        session.add(HypothesisReview(
            hypothesis_id=hypothesis_id,
            created_at="2026-01-02T00:00:00",
            model="test-model",
            critique_text="Needs stronger evidence.",
            unsupported_claims_json='["Claim A"]',
            missing_confounds_json='["Age"]',
            suggested_revisions="Narrow the claim.",
            status=status,
        ))


def test_get_hypothesis_reviews_returns_review_artifacts():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)
    _insert_review(engine, hyp_id)

    resp = client.get(f"/api/research/hypotheses/{hyp_id}/reviews")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["critique_text"] == "Needs stronger evidence."
    assert data[0]["unsupported_claims"] == ["Claim A"]
    assert data[0]["missing_confounds"] == ["Age"]
    assert data[0]["suggested_revisions"] == "Narrow the claim."


def test_get_hypothesis_reviews_hides_dismissed_reviews():
    client, engine = _make_client()
    hyp_id = _insert_hypothesis(engine)
    _insert_review(engine, hyp_id, status="dismissed")

    resp = client.get(f"/api/research/hypotheses/{hyp_id}/reviews")

    assert resp.status_code == 200
    assert resp.json() == []


def test_get_hypothesis_reviews_404_for_unknown_hypothesis():
    client, _ = _make_client()
    resp = client.get("/api/research/hypotheses/9999/reviews")
    assert resp.status_code == 404
