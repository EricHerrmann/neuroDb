"""Tests for GET /api/status route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.status import router


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api")
    return app


def test_get_status_returns_ok_with_engine():
    # StaticPool ensures all connections share the same in-memory SQLite DB,
    # so tables created by create_all are visible inside the request handler.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    client = TestClient(_make_app(engine))
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "db_tables" in data
    assert isinstance(data["db_tables"], list)
    assert "research_questions" in data["db_tables"]
