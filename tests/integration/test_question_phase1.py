"""Integration test T6: create question → confirm topic → filter by topic."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def client_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return TestClient(app), engine


def _seed_topic(engine, name: str) -> int:
    """Seed a topic grouping and return its id (the unified engine replaced topics)."""
    from neurodb.db.grouping_store import get_or_create_grouping
    with Session(engine) as session:
        g = get_or_create_grouping(session, "topic", name)
        session.commit()
        return g.id


def test_create_then_confirm_topic_then_filter(client_engine):
    client, engine = client_engine

    topic_id = _seed_topic(engine, "plasticity")

    # Create question via API — suppress background matcher thread
    with patch("threading.Thread"):
        resp = client.post("/api/research/questions", json={
            "question": "How does plasticity shape memory circuits?",
            "topic_context": "neuroscience",
        })
    assert resp.status_code == 200
    q_id = resp.json()["id"]

    # Add a pending grouping link manually (simulates what the background matcher would create)
    from neurodb.db.grouping_store import link_grouping
    with Session(engine) as session:
        link_grouping(session, topic_id, "question", q_id, status="pending")
        session.commit()

    # Confirm the topic link via PATCH
    resp = client.patch(f"/api/research/questions/{q_id}/topics/{topic_id}", json={"status": "confirmed"})
    assert resp.status_code == 200

    # GET detail — should show confirmed topic
    resp = client.get(f"/api/research/questions/{q_id}")
    assert resp.status_code == 200
    data = resp.json()
    confirmed = [t for t in data["topics"] if t["status"] == "confirmed"]
    assert any(t["topic_id"] == topic_id for t in confirmed), "confirmed topic not in detail response"

    # Filter list by topic — should return this question
    resp = client.get(f"/api/research/questions?topic_id={topic_id}")
    assert resp.status_code == 200
    ids = [q["id"] for q in resp.json()]
    assert q_id in ids, f"question {q_id} not returned when filtering by topic {topic_id}"
