"""Phase 4 integration: context modes over topic/question local evidence."""
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.agents.context_orchestrator import build_context_bundle
from neurodb.db.claim_store import add_gap, create_claim, update_claim_status
from neurodb.db.topic_store import get_or_create_topic, link_paper_topic
from neurodb.schema import Base, Paper, ResearchQuestion


def _engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _seed(engine):
    with Session(engine) as session:
        now = datetime.now(UTC).isoformat()
        topic = get_or_create_topic(session, "stroke recovery")
        paper = Paper(
            title="Motor Recovery After Stroke",
            normalized_title="motor recovery after stroke",
            doi="10.integration/phase4",
            source_type="pubmed",
            topic_context="stroke recovery",
            status="approved",
            queued_at=now,
            reviewed_at=now,
            summary="Local approved summary.",
        )
        session.add(paper)
        session.flush()
        link_paper_topic(session, paper.id, topic.id)
        claim = create_claim(session, paper.id, "Remapping supports recovery.", "finding")
        update_claim_status(session, claim.id, "approved")
        question = ResearchQuestion(
            question="Does remapping support stroke recovery?",
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
        return topic.id, question.id


def test_same_message_has_mode_specific_context_behavior():
    engine = _engine()
    topic_id, question_id = _seed(engine)

    general = build_context_bundle(
        engine,
        request={
            "mode": "general",
            "agent_mode": "neuro_tutor",
            "user_message": "Does remapping support stroke recovery?",
        },
    )
    contextual = build_context_bundle(
        engine,
        request={
            "mode": "contextual",
            "agent_mode": "neuro_tutor",
            "user_message": "Does remapping support stroke recovery?",
            "active_focus": {"focus_type": "topic", "focus_id": topic_id},
        },
    )
    grounded = build_context_bundle(
        engine,
        request={
            "mode": "grounded",
            "agent_mode": "neuro_research",
            "user_message": "Does remapping support stroke recovery?",
            "active_focus": {
                "focus_type": "research_question",
                "focus_id": question_id,
            },
        },
    )

    assert general["source_counts"]["papers"] == 0
    assert contextual["source_counts"]["papers"] == 1
    assert grounded["source_counts"]["claims"] == 1
    assert grounded["source_counts"]["gaps"] == 1
    assert "Grounded mode" in grounded["prompt_block"]
