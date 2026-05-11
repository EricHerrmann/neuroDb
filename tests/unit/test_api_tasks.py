"""Tests for GET /api/tasks/{task_id} route."""
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from neurodb.api.routes.tasks import router
from neurodb.api.tasks import TaskRecord


def _make_app(tasks: dict):
    app = FastAPI()
    app.state.tasks = tasks
    app.include_router(router, prefix="/api")
    return app


def test_get_task_404_for_unknown():
    client = TestClient(_make_app({}))
    resp = client.get("/api/tasks/nonexistent")
    assert resp.status_code == 404


def test_get_task_returns_done_record():
    tasks = {
        "abc": TaskRecord(
            task_id="abc",
            status="done",
            result={"imported": True},
            error=None,
            started_at="2026-01-01T00:00:00+00:00",
            timeout_at="2026-01-01T00:03:00+00:00",
        )
    }
    client = TestClient(_make_app(tasks))
    resp = client.get("/api/tasks/abc")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["result"] == {"imported": True}
    assert data["error"] is None


def test_get_task_running_returns_running_when_not_timed_out():
    future = (datetime.now(UTC) + timedelta(seconds=180)).isoformat()
    tasks = {
        "abc": TaskRecord(
            task_id="abc",
            status="running",
            result=None,
            error=None,
            started_at=datetime.now(UTC).isoformat(),
            timeout_at=future,
        )
    }
    client = TestClient(_make_app(tasks))
    resp = client.get("/api/tasks/abc")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_get_task_returns_failed_when_timeout_at_in_past():
    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    tasks = {
        "abc": TaskRecord(
            task_id="abc",
            status="running",
            result=None,
            error=None,
            started_at="2026-01-01T00:00:00+00:00",
            timeout_at=past,
        )
    }
    client = TestClient(_make_app(tasks))
    resp = client.get("/api/tasks/abc")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert "Timed out" in data["error"]
