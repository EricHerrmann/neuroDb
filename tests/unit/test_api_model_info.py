"""Tests for GET /api/model-info route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_client(router):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_model_info_returns_all_agent_modes():
    from neurodb.api.routes.model_info import router
    client = _make_client(router)
    resp = client.get("/api/model-info")
    assert resp.status_code == 200
    data = resp.json()
    for mode in ("local_db", "external_db", "neuro_tutor", "neuro_research"):
        assert mode in data
        assert "provider" in data[mode]
        assert "model" in data[mode]
        assert isinstance(data[mode]["provider"], str)
        assert isinstance(data[mode]["model"], str)


def test_model_info_values_are_non_empty():
    from neurodb.api.routes.model_info import router
    client = _make_client(router)
    resp = client.get("/api/model-info")
    data = resp.json()
    for mode in ("local_db", "external_db", "neuro_tutor", "neuro_research"):
        assert data[mode]["provider"] != ""
        assert data[mode]["model"] != ""
