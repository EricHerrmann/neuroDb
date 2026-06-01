"""API-level tests for Phase 1 question routes — T5 (delete cascade), T7 (idempotency)."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base, Concept, QuestionConcept, QuestionTopic, ResearchQuestion, Topic


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def client_and_engine():
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


def _seed_question_with_links(engine):
    with Session(engine) as session:
        t = Topic(name="plasticity", description=None, status="active",
                  created_at=_now(), updated_at=_now())
        c = Concept(name="LTP", description=None, status="active",
                    created_at=_now(), updated_at=_now())
        q = ResearchQuestion(
            question="Test?", topic_context="", status="open",
            created_at=_now(), updated_at=_now(),
        )
        session.add_all([t, c, q])
        session.flush()
        session.add(QuestionTopic(question_id=q.id, topic_id=t.id, status="confirmed", created_at=_now()))
        session.add(QuestionConcept(question_id=q.id, concept_id=c.id, status="pending", created_at=_now()))
        session.flush()
        return q.id, t.id, c.id


# --- T5: delete cascade ---

def test_delete_question_returns_204(client_and_engine):
    client, engine = client_and_engine
    q_id, _, _ = _seed_question_with_links(engine)
    resp = client.delete(f"/api/research/questions/{q_id}")
    assert resp.status_code == 204


def test_delete_question_removes_join_rows(client_and_engine):
    client, engine = client_and_engine
    q_id, t_id, c_id = _seed_question_with_links(engine)
    client.delete(f"/api/research/questions/{q_id}")
    with Session(engine) as session:
        qt = session.execute(
            select(QuestionTopic).where(QuestionTopic.question_id == q_id)
        ).scalars().all()
        qc = session.execute(
            select(QuestionConcept).where(QuestionConcept.question_id == q_id)
        ).scalars().all()
        assert len(qt) == 0, "question_topics rows not deleted"
        assert len(qc) == 0, "question_concepts rows not deleted"


def test_delete_question_does_not_remove_topics_or_concepts(client_and_engine):
    client, engine = client_and_engine
    q_id, t_id, c_id = _seed_question_with_links(engine)
    client.delete(f"/api/research/questions/{q_id}")
    with Session(engine) as session:
        assert session.get(Topic, t_id) is not None, "Topic was incorrectly deleted"
        assert session.get(Concept, c_id) is not None, "Concept was incorrectly deleted"


def test_delete_question_404_when_not_found(client_and_engine):
    client, _ = client_and_engine
    resp = client.delete("/api/research/questions/99999")
    assert resp.status_code == 404


def test_deleted_question_returns_404_on_get(client_and_engine):
    client, engine = client_and_engine
    q_id, _, _ = _seed_question_with_links(engine)
    client.delete(f"/api/research/questions/{q_id}")
    resp = client.get(f"/api/research/questions/{q_id}")
    assert resp.status_code == 404


# --- T7: idempotency / unique constraint ---

def test_add_topic_link_twice_does_not_duplicate(client_and_engine):
    client, engine = client_and_engine
    with Session(engine) as session:
        t = Topic(name="memory", description=None, status="active",
                  created_at=_now(), updated_at=_now())
        q = ResearchQuestion(
            question="Test?", topic_context="", status="open",
            created_at=_now(), updated_at=_now(),
        )
        session.add_all([t, q])
        session.flush()
        q_id, t_id = q.id, t.id
    resp1 = client.post(f"/api/research/questions/{q_id}/topics", json={"topic_id": t_id})
    assert resp1.status_code == 200
    resp2 = client.post(f"/api/research/questions/{q_id}/topics", json={"topic_id": t_id})
    # Second call is idempotent — no 409 or 500
    assert resp2.status_code in (200, 204)
    with Session(engine) as session:
        rows = session.execute(
            select(QuestionTopic).where(
                QuestionTopic.question_id == q_id,
                QuestionTopic.topic_id == t_id,
            )
        ).scalars().all()
        assert len(rows) == 1, f"expected 1 row, got {len(rows)}"
