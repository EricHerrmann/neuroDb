"""Tests for POST /api/datasets/{source}/{source_id}/import route."""
from unittest.mock import patch

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
    app.state.tasks = {}
    app.include_router(router, prefix="/api/datasets")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1", notes=None)
        session.add(run)
        session.flush()
        session.add(DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id))
    return TestClient(_make_app(engine)), engine


def test_import_dataset_returns_task_id():
    client, _ = _make_client()
    with patch("neurodb.api.routes.datasets.threading.Thread") as mock_thread:
        mock_thread.return_value.start = lambda: None
        resp = client.post("/api/datasets/openneuro/ds001/import")

    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert isinstance(data["task_id"], str)


def test_import_dataset_task_is_in_store():
    client, _ = _make_client()
    with patch("neurodb.api.routes.datasets.threading.Thread") as mock_thread:
        mock_thread.return_value.start = lambda: None
        resp = client.post("/api/datasets/openneuro/ds001/import")

    task_id = resp.json()["task_id"]
    record = client.app.state.tasks[task_id]
    assert record.status == "running"
    assert record.result is None


def test_import_dataset_404_for_unknown_dataset():
    client, _ = _make_client()
    resp = client.post("/api/datasets/openneuro/unknown-ds/import")
    assert resp.status_code == 404
