"""Unit test for extract_question_topics — keyword matching and pending row persistence (T4)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Concept, QuestionConcept, QuestionTopic, ResearchQuestion, Topic
from neurodb.db.topic_store import extract_question_topics


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def seeded(engine):
    """Returns (question_id, topic_id, concept_id). Topic='plasticity', concept='LTP'."""
    with Session(engine) as session:
        t = Topic(name="plasticity", description=None, status="active",
                  created_at=_now(), updated_at=_now())
        c = Concept(name="LTP", description=None, status="active",
                    created_at=_now(), updated_at=_now())
        q = ResearchQuestion(
            question="Does plasticity involve LTP mechanisms?",
            topic_context="",
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add_all([t, c, q])
        session.flush()
        yield q.id, t.id, c.id


def test_extract_matches_and_persists_pending_rows(engine, seeded):
    q_id, t_id, c_id = seeded
    with Session(engine) as session:
        result = extract_question_topics(session, q_id, "Does plasticity involve LTP mechanisms?")
        session.flush()
        assert "plasticity" in result["suggested_topics"]
        assert "LTP" in result["suggested_concepts"]
        qt = session.execute(
            select(QuestionTopic).where(
                QuestionTopic.question_id == q_id,
                QuestionTopic.topic_id == t_id,
            )
        ).scalar_one_or_none()
        assert qt is not None
        assert qt.status == "pending"
        qc = session.execute(
            select(QuestionConcept).where(
                QuestionConcept.question_id == q_id,
                QuestionConcept.concept_id == c_id,
            )
        ).scalar_one_or_none()
        assert qc is not None
        assert qc.status == "pending"


def test_extract_returns_empty_when_no_match(engine, seeded):
    q_id, _, _ = seeded
    with Session(engine) as session:
        result = extract_question_topics(session, q_id, "completely unrelated question about clouds")
        session.flush()
        assert result["suggested_topics"] == []
        assert result["suggested_concepts"] == []


def test_extract_does_not_create_duplicate_rows(engine, seeded):
    q_id, t_id, c_id = seeded
    with Session(engine) as session:
        extract_question_topics(session, q_id, "Does plasticity involve LTP mechanisms?")
        session.flush()
        # Call again — should not raise or duplicate
        extract_question_topics(session, q_id, "Does plasticity involve LTP mechanisms?")
        session.flush()
        count = session.execute(
            select(QuestionTopic).where(QuestionTopic.question_id == q_id)
        ).scalars().all()
        assert len(count) == 1, "expected exactly one QuestionTopic row"


def test_extract_does_not_create_new_topics(engine, seeded):
    q_id, _, _ = seeded
    with Session(engine) as session:
        before = len(session.execute(select(Topic)).scalars().all())
        extract_question_topics(session, q_id, "some brand new topic that does not exist")
        session.flush()
        after = len(session.execute(select(Topic)).scalars().all())
        assert before == after, "extract_question_topics must not create new topics"
