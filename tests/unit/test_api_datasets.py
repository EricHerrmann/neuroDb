"""Tests for GET /api/datasets route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.datasets import router
from neurodb.db import get_session
from neurodb.schema import Base, DatasetIndex, IngestRun


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/datasets")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_dataset(engine, source: str = "openneuro", source_id: str = "ds001"):
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1", notes=None)
        session.add(run)
        session.flush()
        session.add(DatasetIndex(source=source, source_id=source_id, run_id=run.id))


def test_get_datasets_empty():
    client, _ = _make_client()
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_datasets_returns_rows():
    client, engine = _make_client()
    _insert_dataset(engine, "openneuro", "ds001")

    resp = client.get("/api/datasets")

    data = resp.json()
    assert resp.status_code == 200
    assert len(data) == 1
    assert data[0]["source"] == "openneuro"
    assert data[0]["source_id"] == "ds001"
    assert "title" in data[0]
    assert "modality" in data[0]
    assert "n_subjects" in data[0]


def test_get_datasets_keyword_filter():
    client, engine = _make_client()
    _insert_dataset(engine, "openneuro", "ds001")
    _insert_dataset(engine, "dandi", "000123")

    resp = client.get("/api/datasets?keyword=ds0")

    data = resp.json()
    assert resp.status_code == 200
    assert len(data) == 1
    assert data[0]["source_id"] == "ds001"


def test_get_datasets_modality_filter_returns_empty_when_view_unavailable():
    client, engine = _make_client()
    _insert_dataset(engine, "openneuro", "ds001")

    resp = client.get("/api/datasets?modality=fMRI")

    assert resp.status_code == 200
    assert resp.json() == []
