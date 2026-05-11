"""Tests for /api/knowledge-library routes."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.knowledge_library import router
from neurodb.db import get_session
from neurodb.schema import Base, KnowledgeSource


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/knowledge-library")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_source(engine, title: str = "Test Source", status: str = "pending"):
    with get_session(engine) as session:
        session.add(KnowledgeSource(
            title=title,
            normalized_title=title.lower(),
            source_type="paper",
            topic_context="neuroscience",
            status=status,
            queued_at="2026-01-01T00:00:00",
        ))


def test_get_knowledge_library_empty():
    client, _ = _make_client()
    resp = client.get("/api/knowledge-library")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_knowledge_library_returns_all_by_default():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    _insert_source(engine, "Paper B", "approved")

    resp = client.get("/api/knowledge-library")

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_knowledge_library_filter_by_status():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    _insert_source(engine, "Paper B", "approved")

    resp = client.get("/api/knowledge-library?status=pending")

    data = resp.json()
    assert resp.status_code == 200
    assert len(data) == 1
    assert data[0]["title"] == "Paper A"


def test_approve_source_sets_status():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["reviewed_at"] is not None


def test_reject_source_sets_status():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/reject")

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["reviewed_at"] is not None


def test_approve_source_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/knowledge-library/9999/approve")
    assert resp.status_code == 404
