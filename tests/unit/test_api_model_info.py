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
    assert "agent_modes" in data
    for mode in ("local_db", "external_db", "neuro_tutor", "neuro_research"):
        assert mode in data["agent_modes"]
        assert "tier" in data["agent_modes"][mode]
        assert "provider" in data["agent_modes"][mode]
        assert "model" in data["agent_modes"][mode]
        assert isinstance(data["agent_modes"][mode]["provider"], str)
        assert isinstance(data["agent_modes"][mode]["model"], str)


def test_model_info_returns_low_mid_high_tiers():
    from neurodb.api.routes.model_info import router
    client = _make_client(router)
    resp = client.get("/api/model-info")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["tiers"]) == {"low", "mid", "high"}
    assert data["tiers"]["low"]["tier"] == "economy"
    assert data["tiers"]["mid"]["tier"] == "standard"
    assert data["tiers"]["high"]["tier"] == "premium"
    for tier in ("low", "mid", "high"):
        assert isinstance(data["tiers"][tier]["provider"], str)
        assert isinstance(data["tiers"][tier]["model"], str)


def test_model_info_values_are_non_empty():
    from neurodb.api.routes.model_info import router
    client = _make_client(router)
    resp = client.get("/api/model-info")
    data = resp.json()
    for mode in ("local_db", "external_db", "neuro_tutor", "neuro_research"):
        assert data["agent_modes"][mode]["provider"] != ""
        assert data["agent_modes"][mode]["model"] != ""
    for tier in ("low", "mid", "high"):
        assert data["tiers"][tier]["provider"] != ""
        assert data["tiers"][tier]["model"] != ""
