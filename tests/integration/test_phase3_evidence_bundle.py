"""End-to-end Phase 3 integration: claims, evidence links, research gaps, question bundle."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.db.claim_store import (
    add_evidence_link,
    add_gap,
    create_claim,
    get_evidence_links,
    get_gaps,
    get_question_bundle,
    resolve_gap,
    update_claim_status,
)
from neurodb.db.topic_store import get_or_create_topic, link_paper_topic
from neurodb.schema import (
    Base,
    DatasetIndex,
    DatasetResearchPacket,
    IngestRun,
    Paper,
    ResearchHypothesis,
    ResearchQuestion,
    StudyNote,
)


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


def test_question_linked_to_topic_returns_correct_bundle(engine):
    with Session(engine) as session:
        topic = get_or_create_topic(session, "synaptic plasticity")
        session.flush()

        question = ResearchQuestion(
            question="Does LTP drive long-term memory consolidation?",
            topic_context="synaptic plasticity",
            topic_id=topic.id,
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(question)
        session.commit()

        bundle = get_question_bundle(session, question.id)

    assert bundle["question"]["question"] == "Does LTP drive long-term memory consolidation?"
    assert bundle["topic"]["name"] == "synaptic plasticity"
    assert bundle["hypotheses"] == []
    assert bundle["claims"] == []
    assert bundle["gaps"] == []


def test_approved_claim_from_linked_paper_appears_in_bundle(engine):
    with Session(engine) as session:
        topic = get_or_create_topic(session, "hippocampal plasticity")
        session.flush()

        paper = Paper(
            title="LTP and Memory Consolidation",
            normalized_title="ltp and memory consolidation",
            source_type="paper",
            topic_context="hippocampal plasticity",
            status="approved",
            queued_at=_now(),
        )
        session.add(paper)
        session.flush()
        link_paper_topic(session, paper.id, topic.id)

        question = ResearchQuestion(
            question="How does LTP affect memory?",
            topic_context="hippocampal plasticity",
            topic_id=topic.id,
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(question)
        session.flush()

        claim = create_claim(session, paper.id, "LTP potentiates synaptic weight.", "finding")
        update_claim_status(session, claim.id, "approved")
        session.commit()

        bundle = get_question_bundle(session, question.id)

    assert any(c["text"] == "LTP potentiates synaptic weight." for c in bundle["claims"])


def test_evidence_links_of_all_source_types_stored_and_retrieved(engine):
    with Session(engine) as session:
        paper = Paper(
            title="Plasticity Review",
            normalized_title="plasticity review",
            source_type="paper",
            topic_context="plasticity",
            status="approved",
            queued_at=_now(),
        )
        session.add(paper)
        session.flush()

        question = ResearchQuestion(
            question="What drives plasticity?",
            topic_context="plasticity",
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(question)
        session.flush()

        hypothesis = ResearchHypothesis(
            question_id=question.id,
            title="Plasticity is NMDA-driven",
            mechanism="NMDA activation drives Ca2+ influx.",
            predictions_json="[]",
            limitations="Draft.",
            status="draft",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(hypothesis)
        session.flush()

        # Claim source
        claim = create_claim(session, paper.id, "NMDA drives LTP.", "finding")
        update_claim_status(session, claim.id, "approved")

        # Paper source
        add_evidence_link(session, hypothesis.id, "supports", claim_id=claim.id)
        add_evidence_link(session, hypothesis.id, "contextualizes", paper_id=paper.id)

        # Dataset source
        run = IngestRun(source="openneuro", run_at=_now(), version="1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds000001", run_id=run.id)
        session.add(idx)
        session.flush()
        packet = DatasetResearchPacket(
            index_id=idx.id, source="openneuro", source_id="ds000001",
            title="Hippocampal fMRI Study",
            usefulness_state="partial",
            supported_workflows_json="[]", unsupported_workflows_json="[]",
            missing_context_json="[]", provenance_json="{}", confidence_json="{}",
            harvested_at=_now(), run_id=run.id,
        )
        session.add(packet)
        session.flush()
        add_evidence_link(session, hypothesis.id, "contextualizes", packet_id=packet.id)

        # Note source
        note = StudyNote(paper_id=paper.id, concept_tag="NMDA review", tagged_at=_now())
        session.add(note)
        session.flush()
        add_evidence_link(session, hypothesis.id, "supports", note_id=note.id)

        session.commit()

        links = get_evidence_links(session, hypothesis.id)

    source_types = {lnk["source_type"] for lnk in links}
    assert source_types == {"claim", "paper", "dataset", "note"}


def test_gap_added_appears_in_bundle_and_resolves(engine):
    with Session(engine) as session:
        question = ResearchQuestion(
            question="What limits LTP research?",
            topic_context="plasticity",
            status="open",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(question)
        session.flush()

        gap = add_gap(
            session,
            "No longitudinal human data available.",
            "missing_dataset",
            question_id=question.id,
        )
        session.commit()
        gap_id = gap.id
        q_id = question.id

    with Session(engine) as session:
        bundle = get_question_bundle(session, q_id)
        assert len(bundle["gaps"]) == 1
        assert bundle["gaps"][0]["status"] == "open"

        resolve_gap(session, gap_id)
        session.commit()

        updated_gaps = get_gaps(session, question_id=q_id)
        assert updated_gaps[0]["status"] == "resolved"


def test_hypothesis_with_no_evidence_links_returns_empty_list(engine):
    with Session(engine) as session:
        hypothesis = ResearchHypothesis(
            title="No evidence yet",
            mechanism="Unknown.",
            predictions_json="[]",
            limitations="Draft.",
            status="draft",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(hypothesis)
        session.commit()
        h_id = hypothesis.id

    with Session(engine) as session:
        assert get_evidence_links(session, h_id) == []
