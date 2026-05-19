"""DB epoch — claim, evidence link, and research gap operations."""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from neurodb.schema import (
    Claim,
    DatasetResearchPacket,
    EvidenceLink,
    Paper,
    PaperTopic,
    ResearchGap,
    ResearchHypothesis,
    ResearchQuestion,
    StudyNote,
    Topic,
)

_CLAIM_TYPES = {"finding", "limitation", "method", "question"}
_CLAIM_STATUSES = {"candidate", "approved", "rejected"}
_LINK_TYPES = {"supports", "contradicts", "contextualizes"}
_GAP_TYPES = {
    "missing_dataset", "missing_paper", "missing_evidence",
    "unsupported_claim", "other",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

def create_claim(session: Session, paper_id: int, text: str, claim_type: str) -> Claim:
    if claim_type not in _CLAIM_TYPES:
        raise ValueError(f"Unknown claim_type: {claim_type!r}. Valid: {sorted(_CLAIM_TYPES)}")
    now = _now()
    claim = Claim(
        paper_id=paper_id, text=text, claim_type=claim_type,
        status="candidate", created_at=now, updated_at=now,
    )
    session.add(claim)
    session.flush()
    return claim


def update_claim_status(session: Session, claim_id: int, status: str) -> dict:
    if status not in _CLAIM_STATUSES:
        raise ValueError(f"Unknown status: {status!r}. Valid: {sorted(_CLAIM_STATUSES)}")
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise ValueError(f"Claim {claim_id} not found")
    claim.status = status
    claim.updated_at = _now()
    session.flush()
    return {"id": claim.id, "status": claim.status}


def get_claims_for_paper(session: Session, paper_id: int) -> list[dict]:
    rows = session.execute(
        select(Claim).where(Claim.paper_id == paper_id)
    ).scalars().all()
    return [
        {
            "id": c.id, "text": c.text, "claim_type": c.claim_type,
            "status": c.status, "paper_id": c.paper_id,
        }
        for c in rows
    ]


def get_approved_claims_for_topic(session: Session, topic_id: int) -> list[dict]:
    rows = session.execute(
        select(Claim, Paper)
        .join(Paper, Paper.id == Claim.paper_id)
        .join(PaperTopic, PaperTopic.paper_id == Paper.id)
        .where(PaperTopic.topic_id == topic_id)
        .where(Claim.status == "approved")
    ).all()
    return [
        {
            "id": c.id, "text": c.text, "claim_type": c.claim_type,
            "paper_id": c.paper_id, "paper_title": p.title,
        }
        for c, p in rows
    ]


# ---------------------------------------------------------------------------
# Evidence links
# ---------------------------------------------------------------------------

def add_evidence_link(
    session: Session,
    hypothesis_id: int,
    link_type: str,
    *,
    claim_id: int | None = None,
    paper_id: int | None = None,
    packet_id: int | None = None,
    note_id: int | None = None,
) -> EvidenceLink:
    if link_type not in _LINK_TYPES:
        raise ValueError(f"Unknown link_type: {link_type!r}. Valid: {sorted(_LINK_TYPES)}")
    provided = sum(x is not None for x in [claim_id, paper_id, packet_id, note_id])
    if provided != 1:
        raise ValueError(
            f"Exactly one source FK must be provided; got {provided}. "
            "Pass one of: claim_id, paper_id, packet_id, note_id."
        )

    # Idempotency: return existing link with same (hypothesis, link_type, source)
    existing = session.execute(
        select(EvidenceLink).where(
            EvidenceLink.hypothesis_id == hypothesis_id,
            EvidenceLink.link_type == link_type,
            EvidenceLink.claim_id == claim_id if claim_id is not None
            else EvidenceLink.claim_id.is_(None),
            EvidenceLink.paper_id == paper_id if paper_id is not None
            else EvidenceLink.paper_id.is_(None),
            EvidenceLink.packet_id == packet_id if packet_id is not None
            else EvidenceLink.packet_id.is_(None),
            EvidenceLink.note_id == note_id if note_id is not None
            else EvidenceLink.note_id.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    link = EvidenceLink(
        hypothesis_id=hypothesis_id,
        link_type=link_type,
        claim_id=claim_id,
        paper_id=paper_id,
        packet_id=packet_id,
        note_id=note_id,
        created_at=_now(),
    )
    session.add(link)
    session.flush()
    return link


def get_evidence_links(session: Session, hypothesis_id: int) -> list[dict]:
    rows = session.execute(
        select(EvidenceLink).where(EvidenceLink.hypothesis_id == hypothesis_id)
    ).scalars().all()
    result = []
    for lnk in rows:
        if lnk.claim_id is not None:
            source_type, source_id = "claim", lnk.claim_id
            obj = session.get(Claim, lnk.claim_id)
            summary = (obj.text[:80] if obj else f"claim:{lnk.claim_id}")
        elif lnk.paper_id is not None:
            source_type, source_id = "paper", lnk.paper_id
            obj = session.get(Paper, lnk.paper_id)
            summary = (obj.title[:80] if obj else f"paper:{lnk.paper_id}")
        elif lnk.packet_id is not None:
            source_type, source_id = "dataset", lnk.packet_id
            obj = session.get(DatasetResearchPacket, lnk.packet_id)
            summary = ((obj.title or obj.source_id)[:80] if obj else f"packet:{lnk.packet_id}")
        else:
            source_type, source_id = "note", lnk.note_id
            obj = session.get(StudyNote, lnk.note_id)
            summary = ((obj.note_text or obj.concept_tag)[:80] if obj else f"note:{lnk.note_id}")
        result.append({
            "id": lnk.id,
            "link_type": lnk.link_type,
            "source_type": source_type,
            "source_id": source_id,
            "summary": summary,
        })
    return result


# ---------------------------------------------------------------------------
# Research gaps
# ---------------------------------------------------------------------------

def add_gap(
    session: Session,
    description: str,
    gap_type: str,
    *,
    question_id: int | None = None,
    hypothesis_id: int | None = None,
) -> ResearchGap:
    if gap_type not in _GAP_TYPES:
        raise ValueError(f"Unknown gap_type: {gap_type!r}. Valid: {sorted(_GAP_TYPES)}")
    if question_id is None and hypothesis_id is None:
        raise ValueError("At least one of question_id or hypothesis_id must be provided")
    now = _now()
    gap = ResearchGap(
        question_id=question_id,
        hypothesis_id=hypothesis_id,
        description=description,
        gap_type=gap_type,
        status="open",
        created_at=now,
        updated_at=now,
    )
    session.add(gap)
    session.flush()
    return gap


def resolve_gap(session: Session, gap_id: int) -> dict:
    gap = session.get(ResearchGap, gap_id)
    if gap is None:
        raise ValueError(f"ResearchGap {gap_id} not found")
    gap.status = "resolved"
    gap.updated_at = _now()
    session.flush()
    return {"id": gap.id, "status": gap.status}


def get_gaps(
    session: Session,
    *,
    question_id: int | None = None,
    hypothesis_id: int | None = None,
) -> list[dict]:
    stmt = select(ResearchGap)
    if question_id is not None:
        stmt = stmt.where(ResearchGap.question_id == question_id)
    if hypothesis_id is not None:
        stmt = stmt.where(ResearchGap.hypothesis_id == hypothesis_id)
    rows = session.execute(stmt).scalars().all()
    return [
        {
            "id": g.id,
            "description": g.description,
            "gap_type": g.gap_type,
            "status": g.status,
            "question_id": g.question_id,
            "hypothesis_id": g.hypothesis_id,
        }
        for g in rows
    ]


# ---------------------------------------------------------------------------
# Question bundle
# ---------------------------------------------------------------------------

def get_question_bundle(session: Session, question_id: int) -> dict:
    question = session.get(ResearchQuestion, question_id)
    if question is None:
        return {}

    topic = None
    if question.topic_id is not None:
        topic = session.get(Topic, question.topic_id)

    hypotheses = session.execute(
        select(ResearchHypothesis).where(ResearchHypothesis.question_id == question_id)
    ).scalars().all()

    claims = get_approved_claims_for_topic(session, topic.id) if topic is not None else []
    gaps = get_gaps(session, question_id=question_id)

    return {
        "question": {
            "id": question.id,
            "question": question.question,
            "status": question.status,
            "topic_id": question.topic_id,
        },
        "topic": (
            {"id": topic.id, "name": topic.name, "description": topic.description}
            if topic is not None else None
        ),
        "hypotheses": [
            {"id": h.id, "title": h.title, "status": h.status}
            for h in hypotheses
        ],
        "claims": claims,
        "gaps": [
            {"id": g["id"], "description": g["description"],
             "gap_type": g["gap_type"], "status": g["status"]}
            for g in gaps
        ],
    }
