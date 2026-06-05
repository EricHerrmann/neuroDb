from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.db import init_db
from neurodb.research.learning_plans import propose_plan


@pytest.fixture(autouse=True)
def _no_matcher():
    with patch("neurodb.research.learning_plans.run_suggest_groupings"):
        yield


def _client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return TestClient(app), engine


def test_list_and_get_and_confirm_plan():
    client, engine = _client()
    pid = propose_plan(engine, title="P", origin_prompt="p", origin_agent="tutor",
                       steps=[{"type": "action", "action_text": "x"}])["id"]
    assert any(p["id"] == pid for p in client.get("/api/research/plans?status=proposed").json())
    assert client.get(f"/api/research/plans/{pid}").json()["status"] == "proposed"
    assert client.post(f"/api/research/plans/{pid}/confirm").status_code == 200
    assert client.get(f"/api/research/plans/{pid}").json()["status"] == "active"


def test_confirm_rejects_non_proposed_plan():
    client, engine = _client()
    pid = propose_plan(engine, title="P", origin_prompt="p", origin_agent="tutor",
                       steps=[{"type": "action", "action_text": "x"}])["id"]
    client.post(f"/api/research/plans/{pid}/confirm")
    assert client.post(f"/api/research/plans/{pid}/confirm").status_code == 422


def test_step_progress_and_delete():
    client, engine = _client()
    pid = propose_plan(engine, title="P", origin_prompt="p", origin_agent="tutor",
                       steps=[{"type": "action", "action_text": "x"}])["id"]
    client.post(f"/api/research/plans/{pid}/confirm")
    step_id = client.get(f"/api/research/plans/{pid}").json()["steps"][0]["id"]
    assert client.patch(f"/api/research/plans/{pid}/steps/{step_id}", json={"progress": "done"}).status_code == 200
    assert client.get(f"/api/research/plans/{pid}").json()["percent_complete"] == 100
    assert client.delete(f"/api/research/plans/{pid}").status_code == 200
