"""Tests for POST /api/sql/execute route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.sql import router
from neurodb.schema import Base


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/sql")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def test_execute_simple_query():
    client, _ = _make_client()
    resp = client.post("/api/sql/execute", json={"sql": "SELECT 1 AS n"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["columns"] == ["n"]
    assert data["rows"] == [[1]]
    assert data["row_count"] == 1


def test_execute_query_against_table():
    client, _ = _make_client()
    resp = client.post("/api/sql/execute", json={"sql": "SELECT * FROM ingest_runs LIMIT 5"})
    assert resp.status_code == 200
    data = resp.json()
    assert "columns" in data
    assert data["rows"] == []


def test_execute_invalid_sql_returns_400():
    client, _ = _make_client()
    resp = client.post("/api/sql/execute", json={"sql": "NOT VALID SQL !!!"})
    assert resp.status_code == 400
    assert "detail" in resp.json()
