"""_question_detail sources topics/concepts from the engine (Groupings Phase 3a)."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base, ResearchQuestion
from neurodb.db.grouping_store import get_or_create_grouping, link_grouping


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


def test_detail_reflects_engine_links_and_proposed(client_engine):
    client, engine = client_engine
    with Session(engine) as s:
        q = ResearchQuestion(question="Q?", topic_context="", status="open",
                             created_at=_now(), updated_at=_now())
        s.add(q)
        s.flush()
        qid = q.id
        active = get_or_create_grouping(s, "topic", "stroke")            # active
        prop = get_or_create_grouping(s, "concept", "engram", status="proposed")
        link_grouping(s, active.id, "question", qid, status="confirmed")
        link_grouping(s, prop.id, "question", qid, status="pending")
        s.commit()
        active_id, prop_id = active.id, prop.id

    detail = client.get(f"/api/research/questions/{qid}").json()
    topics = {t["topic_id"]: t for t in detail["topics"]}
    concepts = {c["concept_id"]: c for c in detail["concepts"]}
    assert topics[active_id]["status"] == "confirmed"
    assert topics[active_id]["proposed"] is False
    assert concepts[prop_id]["status"] == "pending"
    assert concepts[prop_id]["proposed"] is True
