"""Tests for GET /api/sessions route."""
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.sessions import router
from neurodb.db import get_session
from neurodb.schema import Base, ChatSession


def _make_app(engine, session_manager=None):
    app = FastAPI()
    app.state.engine = engine
    app.state.session_manager = session_manager
    app.include_router(router, prefix="/api")
    return app


def _make_client(session_manager=None):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine, session_manager)), engine


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


def test_get_active_context_returns_latest_session_topic_without_manager():
    client, engine = _make_client()
    _insert_session(engine, "LTP basics")

    resp = client.get("/api/sessions/active-context")

    assert resp.status_code == 200
    assert resp.json() == {"active_prior_topic": "LTP basics"}


def test_get_active_context_uses_session_manager_when_available():
    manager = MagicMock()
    manager.get_most_recent_session_info.return_value = ("context", "Managed topic")
    client, _engine = _make_client(manager)

    resp = client.get("/api/sessions/active-context")

    assert resp.status_code == 200
    assert resp.json() == {"active_prior_topic": "Managed topic"}
    manager.get_most_recent_session_info.assert_called_once()


def test_end_session_persists_summary_when_sufficient_turns():
    from unittest.mock import MagicMock

    manager = MagicMock()
    manager.end_session.return_value = "Topic: LTP\nSummary"
    client, _ = _make_client(manager)

    resp = client.post("/api/sessions/session-1/end", json={
        "agent_mode": "local_db",
        "messages": [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "two"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "three"},
        ],
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "session-1"
    assert data["message_count"] == 3
    assert data["summary_preview"] == "Topic: LTP\nSummary"
    manager.end_session.assert_called_once()
