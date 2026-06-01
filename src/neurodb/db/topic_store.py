"""DB epoch — topic, concept, and linking table operations."""
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from neurodb.schema import (
    Concept,
    DatasetPacketPaper,
    DatasetPacketTopic,
    DatasetResearchPacket,
    Paper,
    PaperConcept,
    PaperTopic,
    QuestionConcept,
    QuestionTopic,
    StudyNote,
    Topic,
    TopicConcept,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def get_or_create_topic(
    session: Session, name: str, description: str | None = None
) -> Topic:
    name = name.strip()
    existing = session.execute(
        select(Topic).where(Topic.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    now = _now()
    topic = Topic(
        name=name, description=description, status="active",
        created_at=now, updated_at=now,
    )
    session.add(topic)
    session.flush()
    return topic


def get_or_create_concept(
    session: Session, name: str, description: str | None = None
) -> Concept:
    name = name.strip()
    existing = session.execute(
        select(Concept).where(Concept.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    now = _now()
    concept = Concept(
        name=name, description=description, status="active",
        created_at=now, updated_at=now,
    )
    session.add(concept)
    session.flush()
    return concept


def link_paper_topic(session: Session, paper_id: int, topic_id: int) -> None:
    exists = session.execute(
        select(PaperTopic).where(
            PaperTopic.paper_id == paper_id, PaperTopic.topic_id == topic_id
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(PaperTopic(paper_id=paper_id, topic_id=topic_id))
        session.flush()


def link_paper_concept(session: Session, paper_id: int, concept_id: int) -> None:
    exists = session.execute(
        select(PaperConcept).where(
            PaperConcept.paper_id == paper_id, PaperConcept.concept_id == concept_id
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(PaperConcept(paper_id=paper_id, concept_id=concept_id))
        session.flush()


def link_topic_concept(session: Session, topic_id: int, concept_id: int) -> None:
    exists = session.execute(
        select(TopicConcept).where(
            TopicConcept.topic_id == topic_id, TopicConcept.concept_id == concept_id
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(TopicConcept(topic_id=topic_id, concept_id=concept_id))
        session.flush()


def link_packet_topic(session: Session, packet_id: int, topic_id: int) -> None:
    exists = session.execute(
        select(DatasetPacketTopic).where(
            DatasetPacketTopic.packet_id == packet_id,
            DatasetPacketTopic.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(DatasetPacketTopic(packet_id=packet_id, topic_id=topic_id))
        session.flush()


def link_packet_paper(session: Session, packet_id: int, paper_id: int) -> None:
    exists = session.execute(
        select(DatasetPacketPaper).where(
            DatasetPacketPaper.packet_id == packet_id,
            DatasetPacketPaper.paper_id == paper_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(DatasetPacketPaper(packet_id=packet_id, paper_id=paper_id))
        session.flush()


def search_topics(session: Session, query: str, limit: int = 10) -> list[dict]:
    q = f"%{query}%"
    rows = session.execute(
        select(Topic)
        .where(or_(Topic.name.ilike(q), Topic.description.ilike(q)))
        .limit(limit)
    ).scalars().all()
    return [
        {"id": t.id, "name": t.name, "description": t.description, "status": t.status}
        for t in rows
    ]


def get_topic_bundle(session: Session, topic_id: int) -> dict:
    topic = session.get(Topic, topic_id)
    if topic is None:
        return {}

    concepts = session.execute(
        select(Concept)
        .join(TopicConcept, TopicConcept.concept_id == Concept.id)
        .where(TopicConcept.topic_id == topic_id)
    ).scalars().all()

    papers = session.execute(
        select(Paper)
        .join(PaperTopic, PaperTopic.paper_id == Paper.id)
        .where(PaperTopic.topic_id == topic_id)
    ).scalars().all()

    notes = session.execute(
        select(StudyNote).where(StudyNote.topic_id == topic_id)
    ).scalars().all()

    packets = session.execute(
        select(DatasetResearchPacket)
        .join(DatasetPacketTopic, DatasetPacketTopic.packet_id == DatasetResearchPacket.id)
        .where(DatasetPacketTopic.topic_id == topic_id)
    ).scalars().all()

    return {
        "topic": {"id": topic.id, "name": topic.name, "description": topic.description},
        "concepts": [
            {"id": c.id, "name": c.name, "description": c.description} for c in concepts
        ],
        "papers": [
            {"id": p.id, "title": p.title, "doi": p.doi, "status": p.status, "summary": p.summary}
            for p in papers
        ],
        "study_notes": [
            {"id": n.id, "note_text": n.note_text, "concept_tag": n.concept_tag, "tagged_at": n.tagged_at}
            for n in notes
        ],
        "dataset_packets": [
            {"id": pkt.id, "source": pkt.source, "source_id": pkt.source_id,
             "title": pkt.title, "usefulness_state": pkt.usefulness_state}
            for pkt in packets
        ],
    }


def link_question_topic(session: Session, question_id: int, topic_id: int, status: str = "confirmed") -> None:
    """Create a question→topic link. Skips if the link already exists."""
    exists = session.execute(
        select(QuestionTopic).where(
            QuestionTopic.question_id == question_id,
            QuestionTopic.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(QuestionTopic(
            question_id=question_id,
            topic_id=topic_id,
            status=status,
            created_at=_now(),
        ))
        session.flush()


def update_question_topic_status(session: Session, question_id: int, topic_id: int, status: str) -> bool:
    """Update status on an existing question→topic link. Returns True if found."""
    row = session.execute(
        select(QuestionTopic).where(
            QuestionTopic.question_id == question_id,
            QuestionTopic.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    row.status = status
    session.flush()
    return True


def unlink_question_topic(session: Session, question_id: int, topic_id: int) -> bool:
    """Delete a question→topic link. Returns True if found."""
    row = session.execute(
        select(QuestionTopic).where(
            QuestionTopic.question_id == question_id,
            QuestionTopic.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def link_question_concept(session: Session, question_id: int, concept_id: int, status: str = "confirmed") -> None:
    """Create a question→concept link. Skips if the link already exists."""
    exists = session.execute(
        select(QuestionConcept).where(
            QuestionConcept.question_id == question_id,
            QuestionConcept.concept_id == concept_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(QuestionConcept(
            question_id=question_id,
            concept_id=concept_id,
            status=status,
            created_at=_now(),
        ))
        session.flush()


def update_question_concept_status(session: Session, question_id: int, concept_id: int, status: str) -> bool:
    """Update status on an existing question→concept link. Returns True if found."""
    row = session.execute(
        select(QuestionConcept).where(
            QuestionConcept.question_id == question_id,
            QuestionConcept.concept_id == concept_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    row.status = status
    session.flush()
    return True


def unlink_question_concept(session: Session, question_id: int, concept_id: int) -> bool:
    """Delete a question→concept link. Returns True if found."""
    row = session.execute(
        select(QuestionConcept).where(
            QuestionConcept.question_id == question_id,
            QuestionConcept.concept_id == concept_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def extract_question_topics(session: Session, question_id: int, question_text: str) -> dict:
    """Match question text against existing topics/concepts; persist pending rows. Does not create new topics."""
    question_lower = question_text.lower()

    all_topics = session.execute(
        select(Topic).where(Topic.status == "active")
    ).scalars().all()
    suggested_topics = []
    for topic in all_topics:
        if topic.name.lower() in question_lower:
            existing = session.execute(
                select(QuestionTopic).where(
                    QuestionTopic.question_id == question_id,
                    QuestionTopic.topic_id == topic.id,
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(QuestionTopic(
                    question_id=question_id,
                    topic_id=topic.id,
                    status="pending",
                    created_at=_now(),
                ))
                suggested_topics.append(topic.name)

    all_concepts = session.execute(
        select(Concept).where(Concept.status == "active")
    ).scalars().all()
    suggested_concepts = []
    for concept in all_concepts:
        if concept.name.lower() in question_lower:
            existing = session.execute(
                select(QuestionConcept).where(
                    QuestionConcept.question_id == question_id,
                    QuestionConcept.concept_id == concept.id,
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(QuestionConcept(
                    question_id=question_id,
                    concept_id=concept.id,
                    status="pending",
                    created_at=_now(),
                ))
                suggested_concepts.append(concept.name)

    session.flush()
    return {
        "question_id": question_id,
        "suggested_topics": suggested_topics,
        "suggested_concepts": suggested_concepts,
    }
