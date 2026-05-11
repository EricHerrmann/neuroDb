"""Tests for GET /api/sessions route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, ChatSession
from neurodb.api.routes.sessions import router
from neurodb.db import get_session


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_session(engine, topic: str, mode: str = "local_db"):
    with get_session(engine) as session:
        session.add(ChatSession(
            session_id=f"sess-{topic}",
            inferred_topic=topic,
            agent_mode=mode,
            started_at="2026-01-01T00:00:00",
            message_count=3,
        ))


def test_get_sessions_empty():
    client, _ = _make_client()
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_sessions_returns_rows():
    client, engine = _make_client()
    _insert_session(engine, "LTP basics")
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["inferred_topic"] == "LTP basics"
    assert data[0]["agent_mode"] == "local_db"
    assert "session_id" in data[0]


def test_get_sessions_ordered_most_recent_first():
    client, engine = _make_client()
    with get_session(engine) as session:
        session.add(ChatSession(session_id="a", inferred_topic="older", agent_mode="local_db",
                                started_at="2026-01-01T00:00:00", message_count=1))
        session.add(ChatSession(session_id="b", inferred_topic="newer", agent_mode="local_db",
                                started_at="2026-02-01T00:00:00", message_count=1))
    resp = client.get("/api/sessions")
    data = resp.json()
    assert data[0]["inferred_topic"] == "newer"
    assert data[1]["inferred_topic"] == "older"
