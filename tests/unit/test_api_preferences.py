"""Tests for GET /api/preferences and PUT /api/preferences/agent-mode routes."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.preferences import router


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


def test_get_preferences_returns_defaults():
    client, _ = _make_client()
    resp = client.get("/api/preferences")
    assert resp.status_code == 200
    data = resp.json()
    assert "agent_mode" in data
    assert "relevance_threshold" in data
    assert data["agent_mode"] == "local_db"
    assert isinstance(data["relevance_threshold"], float)


def test_get_preferences_returns_saved_agent_mode():
    client, engine = _make_client()
    # Save a mode directly via PUT first
    put_resp = client.put("/api/preferences/agent-mode", json={"mode": "neuro_tutor"})
    assert put_resp.status_code == 200
    # GET should reflect the saved mode
    resp = client.get("/api/preferences")
    assert resp.status_code == 200
    assert resp.json()["agent_mode"] == "neuro_tutor"


def test_put_agent_mode_persists_and_returns_new_mode():
    client, _ = _make_client()
    put_resp = client.put("/api/preferences/agent-mode", json={"mode": "neuro_research"})
    assert put_resp.status_code == 200
    assert put_resp.json()["agent_mode"] == "neuro_research"
    # Confirm persistence via GET
    get_resp = client.get("/api/preferences")
    assert get_resp.status_code == 200
    assert get_resp.json()["agent_mode"] == "neuro_research"


def test_put_agent_mode_rejects_unknown_mode():
    client, _ = _make_client()
    resp = client.put("/api/preferences/agent-mode", json={"mode": "invalid"})
    assert resp.status_code == 400
