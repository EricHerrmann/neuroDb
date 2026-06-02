from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import (
    Base, Claim, DatasetIndex, DatasetResearchPacket, IngestRun,
    Paper, ResearchHypothesis, ResearchQuestion, StudyNote,
)
from neurodb.db.grouping_store import get_or_create_grouping, link_grouping
from neurodb.db.claim_store import (
    add_evidence_link,
    add_gap,
    create_claim,
    get_approved_claims_for_grouping,
    get_approved_claims_for_topic,
    get_claims_for_paper,
    get_evidence_links,
    get_gaps,
    get_question_bundle,
    resolve_gap,
    update_claim_status,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_paper(session, doi="10.1234/test"):
    paper = Paper(
        title="LTP Study", normalized_title=f"ltp study {doi}",
        doi=doi, source_type="paper", topic_context="plasticity",
        status="approved", queued_at=_now(),
    )
    session.add(paper)
    session.flush()
    return paper


def _make_hypothesis(session, question_id=None):
    h = ResearchHypothesis(
        question_id=question_id, title="Test hypothesis",
        mechanism="LTP drives learning.", predictions_json="[]",
        limitations="draft", status="draft",
        created_at=_now(), updated_at=_now(),
    )
    session.add(h)
    session.flush()
    return h


def _make_question(session, topic_id=None):
    q = ResearchQuestion(
        question="Does LTP drive learning?",
        topic_context="plasticity",
        topic_id=topic_id,
        status="open",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(q)
    session.flush()
    return q


def _make_packet(session):
    run = IngestRun(source="test", run_at=_now(), version="1")
    session.add(run)
    session.flush()
    idx = DatasetIndex(source="test", source_id="ds1", run_id=run.id)
    session.add(idx)
    session.flush()
    packet = DatasetResearchPacket(
        index_id=idx.id, source="test", source_id="ds1",
        usefulness_state="partial",
        supported_workflows_json="[]", unsupported_workflows_json="[]",
        missing_context_json="[]", provenance_json="{}", confidence_json="{}",
        harvested_at=_now(), run_id=run.id,
    )
    session.add(packet)
    session.flush()
    return packet


# --- create_claim ---

def test_create_claim_persists_with_candidate_status(session):
    paper = _make_paper(session)
    claim = create_claim(session, paper.id, "LTP increases synaptic weight.", "finding")
    session.commit()
    assert claim.id is not None
    assert claim.status == "candidate"
    assert claim.claim_type == "finding"


def test_create_claim_raises_for_unknown_type(session):
    paper = _make_paper(session)
    with pytest.raises(ValueError, match="Unknown claim_type"):
        create_claim(session, paper.id, "Some claim.", "invalid_type")


# --- update_claim_status ---

def test_update_claim_status_approves(session):
    paper = _make_paper(session)
    claim = create_claim(session, paper.id, "Key finding.", "finding")
    session.flush()
    result = update_claim_status(session, claim.id, "approved")
    assert result == {"id": claim.id, "status": "approved"}
    assert claim.status == "approved"


def test_update_claim_status_rejects(session):
    paper = _make_paper(session)
    claim = create_claim(session, paper.id, "Dubious claim.", "finding")
    session.flush()
    result = update_claim_status(session, claim.id, "rejected")
    assert result["status"] == "rejected"


def test_update_claim_status_raises_for_unknown_status(session):
    paper = _make_paper(session)
    claim = create_claim(session, paper.id, "Some finding.", "finding")
    session.flush()
    with pytest.raises(ValueError, match="Unknown status"):
        update_claim_status(session, claim.id, "published")


def test_update_claim_status_raises_for_unknown_id(session):
    with pytest.raises(ValueError, match="not found"):
        update_claim_status(session, 9999, "approved")


# --- get_claims_for_paper ---

def test_get_claims_for_paper_returns_only_that_paper(session):
    paper_a = _make_paper(session, doi="10.1/a")
    paper_b = _make_paper(session, doi="10.1/b")
    create_claim(session, paper_a.id, "Claim A.", "finding")
    create_claim(session, paper_b.id, "Claim B.", "limitation")
    session.flush()

    results = get_claims_for_paper(session, paper_a.id)
    assert len(results) == 1
    assert results[0]["text"] == "Claim A."


def test_get_claims_for_paper_returns_dict_shape(session):
    paper = _make_paper(session)
    create_claim(session, paper.id, "Finding.", "finding")
    session.flush()
    results = get_claims_for_paper(session, paper.id)
    assert {"id", "text", "claim_type", "status", "paper_id"}.issubset(results[0].keys())


# --- get_approved_claims_for_topic ---

def test_get_approved_claims_for_topic_returns_only_approved(session):
    paper = _make_paper(session)
    topic = get_or_create_grouping(session, "topic", "plasticity")
    session.flush()
    link_grouping(session, topic.id, "paper", paper.id, status="confirmed")

    c_approved = create_claim(session, paper.id, "LTP is real.", "finding")
    c_candidate = create_claim(session, paper.id, "Maybe LTP matters.", "question")
    update_claim_status(session, c_approved.id, "approved")
    session.flush()

    results = get_approved_claims_for_topic(session, topic.id)
    texts = [r["text"] for r in results]
    assert "LTP is real." in texts
    assert "Maybe LTP matters." not in texts


def test_get_approved_claims_for_topic_includes_paper_title(session):
    paper = _make_paper(session)
    topic = get_or_create_grouping(session, "topic", "memory")
    session.flush()
    link_grouping(session, topic.id, "paper", paper.id, status="confirmed")
    claim = create_claim(session, paper.id, "Key finding.", "finding")
    update_claim_status(session, claim.id, "approved")
    session.flush()

    results = get_approved_claims_for_topic(session, topic.id)
    assert results[0]["paper_title"] == "LTP Study"


def test_get_approved_claims_for_grouping(session):
    paper = _make_paper(session)
    claim = create_claim(session, paper.id, "claim A", "finding")
    update_claim_status(session, claim.id, "approved")
    grouping = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, grouping.id, "paper", paper.id, status="confirmed")

    out = get_approved_claims_for_grouping(session, grouping.id)
    assert [c["text"] for c in out] == ["claim A"]


# --- add_evidence_link ---

def test_add_evidence_link_with_claim(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    claim = create_claim(session, paper.id, "Finding.", "finding")
    session.flush()

    link = add_evidence_link(session, hyp.id, "supports", claim_id=claim.id)
    assert link.id is not None
    assert link.claim_id == claim.id
    assert link.link_type == "supports"


def test_add_evidence_link_idempotent(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    claim = create_claim(session, paper.id, "Finding.", "finding")
    session.flush()

    link1 = add_evidence_link(session, hyp.id, "supports", claim_id=claim.id)
    link2 = add_evidence_link(session, hyp.id, "supports", claim_id=claim.id)
    assert link1.id == link2.id


def test_add_evidence_link_raises_for_zero_sources(session):
    hyp = _make_hypothesis(session)
    session.flush()
    with pytest.raises(ValueError, match="Exactly one source"):
        add_evidence_link(session, hyp.id, "supports")


def test_add_evidence_link_raises_for_two_sources(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    claim = create_claim(session, paper.id, "Finding.", "finding")
    session.flush()
    with pytest.raises(ValueError, match="Exactly one source"):
        add_evidence_link(session, hyp.id, "supports", claim_id=claim.id, paper_id=paper.id)


def test_add_evidence_link_raises_for_unknown_link_type(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    claim = create_claim(session, paper.id, "Finding.", "finding")
    session.flush()
    with pytest.raises(ValueError, match="Unknown link_type"):
        add_evidence_link(session, hyp.id, "proves", claim_id=claim.id)


# --- get_evidence_links ---

def test_get_evidence_links_returns_correct_shape(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    claim = create_claim(session, paper.id, "A finding.", "finding")
    session.flush()
    add_evidence_link(session, hyp.id, "supports", claim_id=claim.id)
    session.flush()

    links = get_evidence_links(session, hyp.id)
    assert len(links) == 1
    assert {"id", "link_type", "source_type", "source_id", "summary"}.issubset(links[0].keys())
    assert links[0]["source_type"] == "claim"
    assert links[0]["source_id"] == claim.id


def test_get_evidence_links_returns_empty_when_none(session):
    hyp = _make_hypothesis(session)
    session.flush()
    assert get_evidence_links(session, hyp.id) == []


def test_get_evidence_links_source_type_for_paper(session):
    paper = _make_paper(session)
    hyp = _make_hypothesis(session)
    session.flush()
    add_evidence_link(session, hyp.id, "contextualizes", paper_id=paper.id)
    session.flush()

    links = get_evidence_links(session, hyp.id)
    assert links[0]["source_type"] == "paper"


def test_get_evidence_links_source_type_for_dataset(session):
    packet = _make_packet(session)
    hyp = _make_hypothesis(session)
    session.flush()
    add_evidence_link(session, hyp.id, "contextualizes", packet_id=packet.id)
    session.flush()

    links = get_evidence_links(session, hyp.id)
    assert links[0]["source_type"] == "dataset"


def test_get_evidence_links_source_type_for_note(session):
    hyp = _make_hypothesis(session)
    # SQLite doesn't enforce FK; use paper_id=1 as dummy anchor to satisfy CheckConstraint
    note = StudyNote(paper_id=1, concept_tag="LTP note", tagged_at=_now())
    session.add(note)
    session.flush()
    add_evidence_link(session, hyp.id, "supports", note_id=note.id)
    session.flush()

    links = get_evidence_links(session, hyp.id)
    assert links[0]["source_type"] == "note"


# --- add_gap ---

def test_add_gap_persists_with_open_status(session):
    q = _make_question(session)
    gap = add_gap(session, "No fMRI data.", "missing_dataset", question_id=q.id)
    session.flush()
    assert gap.id is not None
    assert gap.status == "open"


def test_add_gap_raises_when_both_anchors_none(session):
    with pytest.raises(ValueError, match="At least one of"):
        add_gap(session, "No data.", "missing_dataset")


def test_add_gap_raises_for_unknown_gap_type(session):
    q = _make_question(session)
    session.flush()
    with pytest.raises(ValueError, match="Unknown gap_type"):
        add_gap(session, "No data.", "missing_everything", question_id=q.id)


# --- resolve_gap ---

def test_resolve_gap_changes_status(session):
    q = _make_question(session)
    gap = add_gap(session, "No data.", "missing_paper", question_id=q.id)
    session.flush()

    result = resolve_gap(session, gap.id)
    assert result == {"id": gap.id, "status": "resolved"}
    assert gap.status == "resolved"


def test_resolve_gap_raises_for_unknown_id(session):
    with pytest.raises(ValueError, match="not found"):
        resolve_gap(session, 9999)


# --- get_gaps ---

def test_get_gaps_filters_by_question_id(session):
    q_a = _make_question(session)
    q_b = _make_question(session)
    session.flush()
    add_gap(session, "Gap A.", "missing_dataset", question_id=q_a.id)
    add_gap(session, "Gap B.", "missing_paper", question_id=q_b.id)
    session.flush()

    gaps = get_gaps(session, question_id=q_a.id)
    assert len(gaps) == 1
    assert gaps[0]["description"] == "Gap A."


def test_get_gaps_filters_by_hypothesis_id(session):
    h = _make_hypothesis(session)
    session.flush()
    add_gap(session, "Hyp gap.", "unsupported_claim", hypothesis_id=h.id)
    session.flush()

    gaps = get_gaps(session, hypothesis_id=h.id)
    assert len(gaps) == 1
    assert gaps[0]["description"] == "Hyp gap."


def test_get_gaps_returns_open_and_resolved(session):
    q = _make_question(session)
    g1 = add_gap(session, "Open.", "missing_dataset", question_id=q.id)
    g2 = add_gap(session, "Resolved.", "missing_paper", question_id=q.id)
    session.flush()
    resolve_gap(session, g2.id)
    session.flush()

    gaps = get_gaps(session, question_id=q.id)
    statuses = {g["status"] for g in gaps}
    assert "open" in statuses
    assert "resolved" in statuses


# --- get_question_bundle ---

def test_get_question_bundle_returns_empty_for_unknown(session):
    assert get_question_bundle(session, 9999) == {}


def test_get_question_bundle_returns_correct_shape(session):
    q = _make_question(session)
    topic = get_or_create_grouping(session, "topic", "hippocampal plasticity")
    link_grouping(session, topic.id, "question", q.id, status="confirmed")
    h = _make_hypothesis(session, question_id=q.id)
    session.flush()
    add_gap(session, "Need more data.", "missing_dataset", question_id=q.id)
    session.flush()

    bundle = get_question_bundle(session, q.id)

    assert set(bundle.keys()) == {"question", "topics", "hypotheses", "claims", "gaps"}
    assert bundle["question"]["id"] == q.id
    assert bundle["topics"][0]["name"] == "hippocampal plasticity"
    assert any(h_item["id"] == h.id for h_item in bundle["hypotheses"])
    assert len(bundle["gaps"]) == 1


def test_get_question_bundle_topics_empty_when_no_grouping_links(session):
    q = _make_question(session)
    session.flush()
    bundle = get_question_bundle(session, q.id)
    assert bundle["topics"] == []


def test_get_question_bundle_uses_engine_topics(session):
    q = _make_question(session)
    topic = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, topic.id, "question", q.id, status="confirmed")
    paper = _make_paper(session)
    link_grouping(session, topic.id, "paper", paper.id, status="confirmed")
    claim = create_claim(session, paper.id, "claim A", "finding")
    update_claim_status(session, claim.id, "approved")

    bundle = get_question_bundle(session, q.id)
    assert [t["name"] for t in bundle["topics"]] == ["stroke"]
    assert [c["text"] for c in bundle["claims"]] == ["claim A"]


def test_get_gaps_no_filter_returns_all_gaps(session):
    q_a = _make_question(session)
    q_b = _make_question(session)
    session.flush()
    add_gap(session, "Gap A.", "missing_dataset", question_id=q_a.id)
    add_gap(session, "Gap B.", "missing_paper", question_id=q_b.id)
    session.flush()

    all_gaps = get_gaps(session)
    assert len(all_gaps) >= 2
