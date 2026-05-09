"""Tests for list_research_questions and list_hypotheses public helpers."""
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.schema import Base, ResearchHypothesis, ResearchQuestion


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _now():
    return datetime.now(timezone.utc).isoformat()


def _add_question(session, question: str, status: str):
    now = _now()
    row = ResearchQuestion(
        question=question,
        topic_context="test context",
        status=status,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return row


def _add_hypothesis(session, title: str, status: str):
    now = _now()
    row = ResearchHypothesis(
        title=title,
        mechanism="test mechanism",
        evidence_json="[]",
        predictions_json="[]",
        datasets_json="[]",
        confounds_json='["task differences"]',
        limitations="test limitations",
        status=status,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return row


def test_list_research_questions_returns_all_by_default():
    from neurodb.research_tools import list_research_questions

    engine = _engine()
    with Session(engine) as session:
        _add_question(session, "Q1 open", "open")
        _add_question(session, "Q2 parked", "parked")
        session.commit()

    results = list_research_questions(engine)
    assert len(results) == 2
    statuses = {r.status for r in results}
    assert statuses == {"open", "parked"}


def test_list_research_questions_filters_by_status():
    from neurodb.research_tools import list_research_questions

    engine = _engine()
    with Session(engine) as session:
        _add_question(session, "Q1 open", "open")
        _add_question(session, "Q2 parked", "parked")
        session.commit()

    results = list_research_questions(engine, status="open")
    assert len(results) == 1
    assert results[0].status == "open"


def test_list_hypotheses_returns_all_by_default():
    from neurodb.research_tools import list_hypotheses

    engine = _engine()
    with Session(engine) as session:
        _add_hypothesis(session, "H1 draft", "draft")
        _add_hypothesis(session, "H2 needs_evidence", "needs_evidence")
        session.commit()

    results = list_hypotheses(engine)
    assert len(results) == 2
    statuses = {r.status for r in results}
    assert statuses == {"draft", "needs_evidence"}


def test_list_hypotheses_filters_by_status():
    from neurodb.research_tools import list_hypotheses

    engine = _engine()
    with Session(engine) as session:
        _add_hypothesis(session, "H1 draft", "draft")
        _add_hypothesis(session, "H2 needs_evidence", "needs_evidence")
        session.commit()

    results = list_hypotheses(engine, status="draft")
    assert len(results) == 1
    assert results[0].status == "draft"
