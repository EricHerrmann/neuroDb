import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Claim, EvidenceLink, ResearchGap, ResearchHypothesis, ResearchQuestion


def _engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


# --- Table structure ---

def test_claims_table_exists():
    assert "claims" in inspect(_engine()).get_table_names()


def test_evidence_links_table_exists():
    assert "evidence_links" in inspect(_engine()).get_table_names()


def test_research_gaps_table_exists():
    assert "research_gaps" in inspect(_engine()).get_table_names()


def test_claims_has_expected_columns():
    cols = {c.key for c in Claim.__table__.columns}
    assert {"id", "paper_id", "text", "claim_type", "status", "created_at", "updated_at"} <= cols


def test_evidence_links_has_expected_columns():
    cols = {c.key for c in EvidenceLink.__table__.columns}
    assert {
        "id", "hypothesis_id", "claim_id", "paper_id",
        "packet_id", "note_id", "link_type", "created_at",
    } <= cols


def test_research_gaps_has_expected_columns():
    cols = {c.key for c in ResearchGap.__table__.columns}
    assert {
        "id", "question_id", "hypothesis_id", "description",
        "gap_type", "status", "created_at", "updated_at",
    } <= cols


def test_research_question_has_topic_id():
    cols = {c.key for c in ResearchQuestion.__table__.columns}
    assert "topic_id" in cols


# --- EvidenceLink CheckConstraint ---

def test_evidence_link_rejects_zero_sources():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports", created_at="2026-01-01T00:00:00",
        ))
        with pytest.raises(IntegrityError):
            session.flush()


def test_evidence_link_rejects_two_sources():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports",
            claim_id=1, paper_id=2,
            created_at="2026-01-01T00:00:00",
        ))
        with pytest.raises(IntegrityError):
            session.flush()


def test_evidence_link_accepts_claim_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports", claim_id=1,
            created_at="2026-01-01T00:00:00",
        ))
        session.flush()  # must not raise


def test_evidence_link_accepts_paper_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports", paper_id=1,
            created_at="2026-01-01T00:00:00",
        ))
        session.flush()


def test_evidence_link_accepts_packet_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports", packet_id=1,
            created_at="2026-01-01T00:00:00",
        ))
        session.flush()


def test_evidence_link_accepts_note_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(EvidenceLink(
            hypothesis_id=1, link_type="supports", note_id=1,
            created_at="2026-01-01T00:00:00",
        ))
        session.flush()


# --- ResearchGap CheckConstraint ---

def test_research_gap_rejects_both_anchors_null():
    engine = _engine()
    with Session(engine) as session:
        session.add(ResearchGap(
            description="Missing data", gap_type="missing_dataset",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        ))
        with pytest.raises(IntegrityError):
            session.flush()


def test_research_gap_accepts_question_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(ResearchGap(
            question_id=1, description="Need more data", gap_type="missing_dataset",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        ))
        session.flush()


def test_research_gap_accepts_hypothesis_only():
    engine = _engine()
    with Session(engine) as session:
        session.add(ResearchGap(
            hypothesis_id=1, description="Need more data", gap_type="missing_paper",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        ))
        session.flush()


# --- ResearchHypothesis nullable fields ---

def test_research_hypothesis_accepts_null_evidence_json():
    engine = _engine()
    with Session(engine) as session:
        session.add(ResearchHypothesis(
            title="Test", mechanism="mechanism",
            evidence_json=None, datasets_json=None, confounds_json=None,
            predictions_json="[]", limitations="none",
            status="draft",
            created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        ))
        session.flush()
