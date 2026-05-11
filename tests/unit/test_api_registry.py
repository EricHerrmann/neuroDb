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
