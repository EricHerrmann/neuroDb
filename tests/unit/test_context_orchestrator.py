from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.agents.context_orchestrator import (
    DEFAULT_CONTEXT_MODE,
    build_context_bundle,
    context_summary_event,
    normalize_context_mode,
)
from neurodb.db.claim_store import add_gap, create_claim, update_claim_status
from neurodb.db.topic_store import (
    get_or_create_concept,
    get_or_create_topic,
    link_paper_topic,
    link_topic_concept,
)
from neurodb.schema import Base, Paper, ResearchQuestion, StudyNote


class _SearchStore:
    def __init__(self, rows):
        self.rows = rows

    def search(self, query, n=3):
        assert query
        return self.rows[:n]


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


def _seed_topic(engine):
    with Session(engine) as session:
        now = datetime.now(UTC).isoformat()
        topic = get_or_create_topic(session, "stroke recovery", "Recovery after stroke")
        concept = get_or_create_concept(session, "cortical remapping")
        link_topic_concept(session, topic.id, concept.id)
        paper = Paper(
            title="Motor Recovery After Stroke",
            normalized_title="motor recovery after stroke",
            doi="10.test/stroke",
            source_type="pubmed",
            topic_context="stroke recovery",
            status="approved",
            queued_at=now,
            reviewed_at=now,
            summary="Summary",
        )
        session.add(paper)
        session.flush()
        link_paper_topic(session, paper.id, topic.id)
        session.add(StudyNote(topic_id=topic.id, concept_tag="remapping", tagged_at=now))
        session.commit()
        return topic.id


def _seed_question(engine):
    with Session(engine) as session:
        now = datetime.now(UTC).isoformat()
        topic = get_or_create_topic(session, "stroke recovery", "Recovery after stroke")
        paper = Paper(
            title="Motor Recovery After Stroke",
            normalized_title="motor recovery after stroke",
            doi="10.test/stroke-question",
            source_type="pubmed",
            topic_context="stroke recovery",
            status="approved",
            queued_at=now,
        )
        session.add(paper)
        session.flush()
        link_paper_topic(session, paper.id, topic.id)
        claim = create_claim(session, paper.id, "Remapping supports recovery.", "finding")
        update_claim_status(session, claim.id, "approved")
        question = ResearchQuestion(
            question="Does remapping improve recovery?",
            topic_context="stroke recovery",
            status="open",
            created_at=now,
            updated_at=now,
            topic_id=topic.id,
        )
        session.add(question)
        session.flush()
        add_gap(session, "No lesion-location dataset.", "missing_dataset", question_id=question.id)
        session.commit()
        return question.id


def test_normalize_context_mode_defaults_and_validates():
    assert normalize_context_mode(None) == DEFAULT_CONTEXT_MODE
    assert normalize_context_mode("Grounded") == "grounded"
    with pytest.raises(ValueError):
        normalize_context_mode("strict")


def test_contextual_topic_focus_returns_topic_bundle_counts(engine):
    topic_id = _seed_topic(engine)
    bundle = build_context_bundle(
        engine,
        request={
            "mode": "contextual",
            "agent_mode": "neuro_tutor",
            "user_message": "stroke recovery",
            "active_focus": {"focus_type": "topic", "focus_id": topic_id},
        },
    )
    assert bundle["mode"] == "contextual"
    assert bundle["topic_bundle"]["topic"]["name"] == "stroke recovery"
    assert bundle["source_counts"]["papers"] == 1
    assert bundle["source_counts"]["concepts"] == 1
    assert bundle["source_counts"]["study_notes"] == 1
    assert "NeuroDb context mode: contextual" in bundle["prompt_block"]


def test_contextual_question_focus_returns_claims_and_gaps(engine):
    question_id = _seed_question(engine)
    bundle = build_context_bundle(
        engine,
        request={
            "mode": "contextual",
            "agent_mode": "neuro_research",
            "user_message": "Does remapping improve recovery?",
            "active_focus": {"focus_type": "research_question", "focus_id": question_id},
        },
    )
    assert bundle["question_bundle"]["question"]["id"] == question_id
    assert bundle["source_counts"]["claims"] == 1
    assert bundle["source_counts"]["gaps"] == 1
    assert bundle["gap_summaries"][0]["gap_type"] == "missing_dataset"


def test_general_without_focus_skips_local_retrieval(engine):
    _seed_topic(engine)
    bundle = build_context_bundle(
        engine,
        request={
            "mode": "general",
            "agent_mode": "neuro_tutor",
            "user_message": "Explain stroke recovery",
        },
    )
    assert bundle["topic_bundle"] is None
    assert bundle["question_bundle"] is None
    assert all(value == 0 for value in bundle["source_counts"].values())


def test_grounded_without_support_returns_warning(engine):
    bundle = build_context_bundle(
        engine,
        request={
            "mode": "grounded",
            "agent_mode": "neuro_research",
            "user_message": "Use local evidence only",
        },
    )
    assert bundle["warnings"] == ["No approved local support was found for grounded mode."]


def test_old_research_question_schema_does_not_crash_contextual_chat():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with eng.begin() as conn:
        conn.execute(text(
            "CREATE TABLE research_questions ("
            "id INTEGER PRIMARY KEY, "
            "question VARCHAR, "
            "topic_context VARCHAR, "
            "status VARCHAR, "
            "created_at VARCHAR, "
            "updated_at VARCHAR)"
        ))
        conn.execute(text(
            "INSERT INTO research_questions "
            "(id, question, topic_context, status, created_at, updated_at) "
            "VALUES (1, 'Explain cortical remapping after stroke.', "
            "'stroke recovery', 'open', 'now', 'now')"
        ))

    bundle = build_context_bundle(
        eng,
        request={
            "mode": "contextual",
            "agent_mode": "neuro_tutor",
            "user_message": "Explain cortical remapping after stroke.",
        },
    )

    assert bundle["active_focus"] == {
        "focus_type": "research_question",
        "focus_id": 1,
        "label": "Explain cortical remapping after stroke.",
    }
    assert bundle["question_bundle"] is None
    assert "Phase 3 claims/evidence migration" in bundle["warnings"][0]


def test_semantic_hits_count_both_stores(engine):
    bundle = build_context_bundle(
        engine,
        request={
            "mode": "contextual",
            "agent_mode": "neuro_tutor",
            "user_message": "stroke",
        },
        knowledge_store=_SearchStore([{"id": "k1"}]),
        vector_store=_SearchStore([{"id": "v1"}, {"id": "v2"}]),
    )
    assert bundle["source_counts"]["semantic_hits"] == 3


def test_context_summary_event_shape(engine):
    topic_id = _seed_topic(engine)
    bundle = build_context_bundle(
        engine,
        request={
            "mode": "contextual",
            "agent_mode": "neuro_tutor",
            "user_message": "stroke",
            "active_focus": {"focus_type": "topic", "focus_id": topic_id},
        },
    )
    event = context_summary_event(bundle)
    assert event["type"] == "context_summary"
    assert event["context_mode"] == "contextual"
    assert event["source_counts"]["papers"] == 1
