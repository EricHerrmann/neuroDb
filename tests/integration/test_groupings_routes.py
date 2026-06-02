"""API tests for /api/research/groupings (Groupings Phase 3a)."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base
from neurodb.db.grouping_store import get_or_create_grouping


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def client_engine():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return TestClient(app), engine


def test_create_list_and_patch_status(client_engine):
    client, engine = client_engine
    r = client.post("/api/research/groupings",
                    json={"type": "topic", "name": "plasticity"})
    assert r.status_code == 200
    gid = r.json()["id"]
    assert r.json()["status"] == "active"

    listed = client.get("/api/research/groupings?type=topic&status=active").json()
    assert [g["name"] for g in listed] == ["plasticity"]

    # archive via status patch
    patched = client.patch(f"/api/research/groupings/{gid}", json={"status": "archived"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "archived"


def test_reparent_and_invariant_422(client_engine):
    client, engine = client_engine
    with Session(engine) as s:
        parent = get_or_create_grouping(s, "topic", "plasticity")
        child = get_or_create_grouping(s, "topic", "neuroplasticity")
        concept = get_or_create_grouping(s, "concept", "LTP")
        s.commit()
        parent_id, child_id, concept_id = parent.id, child.id, concept.id

    ok = client.patch(f"/api/research/groupings/{child_id}", json={"parent_id": parent_id})
    assert ok.status_code == 200
    assert ok.json()["parent_id"] == parent_id

    # cross-type parent is rejected
    bad = client.patch(f"/api/research/groupings/{concept_id}", json={"parent_id": parent_id})
    assert bad.status_code == 422


def test_unknown_type_422(client_engine):
    client, _ = client_engine
    r = client.post("/api/research/groupings", json={"type": "method", "name": "fMRI"})
    assert r.status_code == 422
