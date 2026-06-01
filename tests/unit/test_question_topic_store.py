"""Unit tests for question_topics and question_concepts join table CRUD (T1, T2)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Concept, QuestionConcept, QuestionTopic, ResearchQuestion, Topic


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
def seed(engine):
    """Returns (question_id, topic_id, concept_id)."""
    with Session(engine) as session:
        q = ResearchQuestion(
            question="Test question?",
            topic_context="",
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(q)
        t = Topic(name="plasticity", description=None, status="active",
                  created_at=_now(), updated_at=_now())
        session.add(t)
        c = Concept(name="LTP", description=None, status="active",
                    created_at=_now(), updated_at=_now())
        session.add(c)
        session.flush()
        yield q.id, t.id, c.id


# --- T1: question_topics ---

def test_question_topic_insert_and_read(engine, seed):
    q_id, t_id, _ = seed
    with Session(engine) as session:
        row = QuestionTopic(question_id=q_id, topic_id=t_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        fetched = session.execute(
            select(QuestionTopic).where(
                QuestionTopic.question_id == q_id,
                QuestionTopic.topic_id == t_id,
            )
        ).scalar_one()
        assert fetched.status == "pending"


def test_question_topic_confirm(engine, seed):
    q_id, t_id, _ = seed
    with Session(engine) as session:
        row = QuestionTopic(question_id=q_id, topic_id=t_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        row.status = "confirmed"
        session.flush()
        fetched = session.execute(
            select(QuestionTopic).where(
                QuestionTopic.question_id == q_id,
                QuestionTopic.topic_id == t_id,
            )
        ).scalar_one()
        assert fetched.status == "confirmed"


def test_question_topic_dismiss_deletes_row(engine, seed):
    q_id, t_id, _ = seed
    with Session(engine) as session:
        row = QuestionTopic(question_id=q_id, topic_id=t_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        session.delete(row)
        session.flush()
        result = session.execute(
            select(QuestionTopic).where(
                QuestionTopic.question_id == q_id,
                QuestionTopic.topic_id == t_id,
            )
        ).scalar_one_or_none()
        assert result is None


def test_question_topic_unique_constraint(engine, seed):
    q_id, t_id, _ = seed
    with Session(engine) as session:
        session.add(QuestionTopic(question_id=q_id, topic_id=t_id, status="pending", created_at=_now()))
        session.flush()
        session.add(QuestionTopic(question_id=q_id, topic_id=t_id, status="confirmed", created_at=_now()))
        with pytest.raises(IntegrityError):
            session.flush()


# --- T2: question_concepts ---

def test_question_concept_insert_and_read(engine, seed):
    q_id, _, c_id = seed
    with Session(engine) as session:
        row = QuestionConcept(question_id=q_id, concept_id=c_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        fetched = session.execute(
            select(QuestionConcept).where(
                QuestionConcept.question_id == q_id,
                QuestionConcept.concept_id == c_id,
            )
        ).scalar_one()
        assert fetched.status == "pending"


def test_question_concept_confirm(engine, seed):
    q_id, _, c_id = seed
    with Session(engine) as session:
        row = QuestionConcept(question_id=q_id, concept_id=c_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        row.status = "confirmed"
        session.flush()
        fetched = session.execute(
            select(QuestionConcept).where(
                QuestionConcept.question_id == q_id,
                QuestionConcept.concept_id == c_id,
            )
        ).scalar_one()
        assert fetched.status == "confirmed"


def test_question_concept_dismiss_deletes_row(engine, seed):
    q_id, _, c_id = seed
    with Session(engine) as session:
        row = QuestionConcept(question_id=q_id, concept_id=c_id, status="pending", created_at=_now())
        session.add(row)
        session.flush()
        session.delete(row)
        session.flush()
        result = session.execute(
            select(QuestionConcept).where(
                QuestionConcept.question_id == q_id,
                QuestionConcept.concept_id == c_id,
            )
        ).scalar_one_or_none()
        assert result is None


def test_question_concept_unique_constraint(engine, seed):
    q_id, _, c_id = seed
    with Session(engine) as session:
        session.add(QuestionConcept(question_id=q_id, concept_id=c_id, status="pending", created_at=_now()))
        session.flush()
        session.add(QuestionConcept(question_id=q_id, concept_id=c_id, status="confirmed", created_at=_now()))
        with pytest.raises(IntegrityError):
            session.flush()
