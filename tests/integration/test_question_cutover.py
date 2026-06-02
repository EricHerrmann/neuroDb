"""create_question wiring + parent-filter rollup over the engine (Groupings Phase 3a)."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base, ResearchQuestion
from neurodb.db.grouping_store import get_or_create_grouping, set_parent, link_grouping


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


def test_create_question_invokes_matcher_wrapper(client_engine):
    client, engine = client_engine
    calls = {}

    def fake_run(engine_arg, *, anchor_type, anchor_id, anchor_text, gtypes=("topic", "concept")):
        calls["anchor_type"] = anchor_type
        calls["anchor_text"] = anchor_text
        calls["gtypes"] = gtypes

    # Run the background work synchronously by stubbing the wrapper and the thread.
    with patch("neurodb.research.grouping_matcher.run_suggest_groupings", fake_run), \
         patch("threading.Thread") as thread_cls:
        thread_cls.side_effect = lambda target, daemon=False: type(
            "T", (), {"start": staticmethod(target)})()
        resp = client.post("/api/research/questions",
                           json={"question": "How does plasticity work?", "topic_context": ""})
    assert resp.status_code == 200
    assert calls["anchor_type"] == "question"
    assert calls["anchor_text"] == "How does plasticity work?"
    assert calls["gtypes"] == ("topic", "concept")


def test_parent_filter_returns_child_tagged_question(client_engine):
    client, engine = client_engine
    with Session(engine) as s:
        q = ResearchQuestion(question="Q?", topic_context="", status="open",
                             created_at=_now(), updated_at=_now())
        s.add(q)
        s.flush()
        qid = q.id
        parent = get_or_create_grouping(s, "topic", "plasticity")
        child = get_or_create_grouping(s, "topic", "neuroplasticity")
        set_parent(s, child.id, parent.id)
        link_grouping(s, child.id, "question", qid, status="confirmed")
        s.commit()
        parent_id, child_id = parent.id, child.id

    by_parent = client.get(f"/api/research/questions?topic_id={parent_id}").json()
    assert [d["id"] for d in by_parent] == [qid]      # rollup includes child
    by_child = client.get(f"/api/research/questions?topic_id={child_id}").json()
    assert [d["id"] for d in by_child] == [qid]       # leaf exact
