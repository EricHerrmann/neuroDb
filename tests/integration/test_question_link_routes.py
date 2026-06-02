"""Per-question link routes operate on grouping_links + proposal lifecycle (3a)."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
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


def _make_question(engine) -> int:
    with Session(engine) as s:
        q = ResearchQuestion(question="Q?", topic_context="", status="open",
                             created_at=_now(), updated_at=_now())
        s.add(q)
        s.flush()
        qid = q.id
        s.commit()
        return qid


def test_add_then_confirm_proposed_topic_activates_grouping(client_engine):
    client, engine = client_engine
    qid = _make_question(engine)
    with Session(engine) as s:
        g = get_or_create_grouping(s, "topic", "plasticity", status="proposed")
        link_grouping(s, g.id, "question", qid, status="pending")
        s.commit()
        gid = g.id

    resp = client.patch(f"/api/research/questions/{qid}/topics/{gid}",
                        json={"status": "confirmed"})
    assert resp.status_code == 200
    with engine.connect() as conn:
        gstatus = conn.execute(text("SELECT status FROM groupings WHERE id=:i"),
                               {"i": gid}).fetchone()[0]
        lstatus = conn.execute(text(
            "SELECT status FROM grouping_links WHERE grouping_id=:i AND anchor_id=:q"),
            {"i": gid, "q": qid}).fetchone()[0]
    assert gstatus == "active"      # proposed -> active on confirm
    assert lstatus == "confirmed"


def test_dismiss_proposed_topic_deletes_orphan_grouping(client_engine):
    client, engine = client_engine
    qid = _make_question(engine)
    with Session(engine) as s:
        g = get_or_create_grouping(s, "topic", "plasticity", status="proposed")
        link_grouping(s, g.id, "question", qid, status="pending")
        s.commit()
        gid = g.id

    resp = client.delete(f"/api/research/questions/{qid}/topics/{gid}")
    assert resp.status_code == 204
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM groupings WHERE id=:i"),
                         {"i": gid}).fetchone()[0]
    assert n == 0      # orphaned proposed grouping cleaned up


def test_dismiss_active_topic_keeps_grouping(client_engine):
    client, engine = client_engine
    qid = _make_question(engine)
    with Session(engine) as s:
        g = get_or_create_grouping(s, "topic", "stroke")  # active
        link_grouping(s, g.id, "question", qid, status="pending")
        s.commit()
        gid = g.id

    client.delete(f"/api/research/questions/{qid}/topics/{gid}")
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM groupings WHERE id=:i"),
                         {"i": gid}).fetchone()[0]
    assert n == 1      # active grouping is never auto-deleted


def test_add_concept_link_via_route(client_engine):
    client, engine = client_engine
    qid = _make_question(engine)
    with Session(engine) as s:
        g = get_or_create_grouping(s, "concept", "LTP")
        s.commit()
        gid = g.id
    resp = client.post(f"/api/research/questions/{qid}/concepts", json={"concept_id": gid})
    assert resp.status_code == 200
    assert any(c["concept_id"] == gid and c["status"] == "confirmed"
               for c in resp.json()["concepts"])
