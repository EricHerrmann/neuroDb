"""Tests for GET /api/registry route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.registry import router
from neurodb.db import get_session
from neurodb.schema import Base, LearningSource


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/registry")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_source(engine, source_type: str = "book", display_name: str = "Test Book"):
    with get_session(engine) as session:
        session.add(LearningSource(
            source_type=source_type,
            source_key=f"key-{display_name}",
            display_name=display_name,
            added_by="user",
            added_at="2026-01-01T00:00:00",
        ))


def test_get_registry_empty():
    client, _ = _make_client()
    resp = client.get("/api/registry")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_registry_returns_rows():
    client, engine = _make_client()
    _insert_source(engine, "book", "Neuroscience by Purves")

    resp = client.get("/api/registry")

    data = resp.json()
    assert resp.status_code == 200
    assert len(data) == 1
    assert data[0]["display_name"] == "Neuroscience by Purves"
    assert data[0]["source_type"] == "book"


def test_get_registry_ordered_by_type_then_name():
    client, engine = _make_client()
    _insert_source(engine, "paper", "Z Paper")
    _insert_source(engine, "book", "A Book")

    resp = client.get("/api/registry")

    data = resp.json()
    assert resp.status_code == 200
    assert data[0]["source_type"] == "book"
    assert data[0]["display_name"] == "A Book"


def test_delete_registry_removes_row_and_returns_204():
    client, engine = _make_client()
    _insert_source(engine, "paper", "LTP Paper")
    item_id = client.get("/api/registry").json()[0]["id"]

    resp = client.delete(f"/api/registry/{item_id}")

    assert resp.status_code == 204
    assert client.get("/api/registry").json() == []


def test_delete_registry_404_for_unknown():
    client, _ = _make_client()
    resp = client.delete("/api/registry/9999")
    assert resp.status_code == 404


def test_post_registry_creates_source_and_returns_item():
    client, _ = _make_client()

    resp = client.post("/api/registry", json={
        "source_type": "paper",
        "source_key": "doi:10.1234/test",
        "display_name": "LTP Review",
        "added_by": "user",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["source_key"] == "doi:10.1234/test"
    assert data["display_name"] == "LTP Review"
    assert data["added_by"] == "user"
    assert "id" in data


def test_post_registry_422_on_missing_field():
    client, _ = _make_client()

    resp = client.post("/api/registry", json={
        "source_type": "paper",
        "source_key": "doi:test",
    })

    assert resp.status_code == 422
