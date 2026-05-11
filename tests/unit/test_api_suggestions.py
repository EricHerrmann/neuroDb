"""Tests for /api/suggestions routes."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.suggestions import router
from neurodb.db import get_session
from neurodb.schema import Base, ImportQueue, LearningSource, SourceSuggestion


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/suggestions")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_import_item(
    engine,
    source_id: str = "ds001",
    status: str = "pending",
    suggested_at: str = "2026-01-01T00:00:00",
):
    with get_session(engine) as session:
        session.add(ImportQueue(
            source="openneuro",
            source_id=source_id,
            title="Test Dataset",
            reason="Relevant to plasticity",
            chapter_ref="chapter-12",
            status=status,
            suggested_at=suggested_at,
        ))


def _insert_source_suggestion(
    engine,
    display_name: str = "Some Paper",
    status: str = "pending",
    suggested_at: str = "2026-01-01T00:00:00",
):
    with get_session(engine) as session:
        session.add(SourceSuggestion(
            suggestion_type="paper",
            reference="10.1234/example",
            display_name=display_name,
            reason="Relevant source",
            status=status,
            suggested_at=suggested_at,
        ))


def test_get_suggestions_empty():
    client, _ = _make_client()
    resp = client.get("/api/suggestions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["import_queue"] == []
    assert data["source_suggestions"] == []


def test_get_suggestions_returns_pending_import_items_only_ordered_newest_first():
    client, engine = _make_client()
    _insert_import_item(engine, "ds001", "pending", "2026-01-01T00:00:00")
    _insert_import_item(engine, "ds002", "dismissed", "2026-02-01T00:00:00")
    _insert_import_item(engine, "ds003", "pending", "2026-03-01T00:00:00")

    resp = client.get("/api/suggestions")

    data = resp.json()
    assert resp.status_code == 200
    assert [item["source_id"] for item in data["import_queue"]] == ["ds003", "ds001"]


def test_get_suggestions_returns_pending_source_suggestions_only_ordered_newest_first():
    client, engine = _make_client()
    _insert_source_suggestion(engine, "Older LTP Paper", "pending", "2026-01-01T00:00:00")
    _insert_source_suggestion(engine, "Dismissed Paper", "dismissed", "2026-02-01T00:00:00")
    _insert_source_suggestion(engine, "Newer LTP Paper", "pending", "2026-03-01T00:00:00")

    resp = client.get("/api/suggestions")

    data = resp.json()
    assert resp.status_code == 200
    assert [item["display_name"] for item in data["source_suggestions"]] == [
        "Newer LTP Paper",
        "Older LTP Paper",
    ]


def test_dismiss_import_item_sets_dismissed():
    client, engine = _make_client()
    _insert_import_item(engine, "ds001", "pending")
    item_id = client.get("/api/suggestions").json()["import_queue"][0]["id"]

    resp = client.post(f"/api/suggestions/import-queue/{item_id}/dismiss")

    assert resp.status_code == 204
    data = client.get("/api/suggestions").json()
    assert data["import_queue"] == []


def test_dismiss_import_item_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/suggestions/import-queue/9999/dismiss")
    assert resp.status_code == 404


def test_dismiss_source_suggestion_returns_204():
    client, engine = _make_client()
    _insert_source_suggestion(engine, "LTP Paper")
    item_id = client.get("/api/suggestions").json()["source_suggestions"][0]["id"]

    resp = client.post(f"/api/suggestions/source-suggestions/{item_id}/dismiss")

    assert resp.status_code == 204
    assert client.get("/api/suggestions").json()["source_suggestions"] == []


def test_dismiss_source_suggestion_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/suggestions/source-suggestions/9999/dismiss")
    assert resp.status_code == 404


def test_promote_source_suggestion_creates_registry_entry_and_returns_item():
    client, engine = _make_client()
    _insert_source_suggestion(engine, "LTP Review")
    item_id = client.get("/api/suggestions").json()["source_suggestions"][0]["id"]

    resp = client.post(f"/api/suggestions/source-suggestions/{item_id}/promote")

    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "LTP Review"
    assert data["added_by"] == "suggestion"
    assert "id" in data
    assert client.get("/api/suggestions").json()["source_suggestions"] == []
    with get_session(engine) as session:
        source = session.get(LearningSource, data["id"])
        assert source is not None
        assert source.source_key == "10.1234/example"


def test_promote_source_suggestion_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/suggestions/source-suggestions/9999/promote")
    assert resp.status_code == 404
