import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import (
    Base, Concept, Topic,
    DatasetPacketPaper, DatasetPacketTopic,
    PaperConcept, PaperTopic, TopicConcept,
    Paper,
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


def test_topic_table_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("topics")}
    assert {"id", "name", "description", "status", "created_at", "updated_at"}.issubset(cols)


def test_concept_table_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("concepts")}
    assert {"id", "name", "description", "status", "created_at", "updated_at"}.issubset(cols)


def test_topic_name_is_unique(engine):
    now = _now()
    with Session(engine) as s:
        s.add(Topic(name="stroke recovery", status="active", created_at=now, updated_at=now))
        s.commit()
    with pytest.raises(IntegrityError):
        with Session(engine) as s:
            s.add(Topic(name="stroke recovery", status="active", created_at=now, updated_at=now))
            s.commit()


def test_concept_name_is_unique(engine):
    now = _now()
    with Session(engine) as s:
        s.add(Concept(name="neuroplasticity", status="active", created_at=now, updated_at=now))
        s.commit()
    with pytest.raises(IntegrityError):
        with Session(engine) as s:
            s.add(Concept(name="neuroplasticity", status="active", created_at=now, updated_at=now))
            s.commit()


def test_topic_description_is_optional(engine):
    now = _now()
    with Session(engine) as s:
        topic = Topic(name="cortical remapping", status="active", created_at=now, updated_at=now)
        s.add(topic)
        s.commit()
        s.refresh(topic)
        assert topic.description is None


def test_linking_tables_all_exist(engine):
    names = set(inspect(engine).get_table_names())
    for t in (
        "paper_topics",
        "paper_concepts",
        "topic_concepts",
        "dataset_packet_topics",
        "dataset_packet_papers",
    ):
        assert t in names, f"Table '{t}' missing"


def test_paper_topics_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("paper_topics")}
    assert {"paper_id", "topic_id"}.issubset(cols)


def test_topic_concepts_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("topic_concepts")}
    assert {"topic_id", "concept_id"}.issubset(cols)


def test_paper_topic_unique_constraint_enforced(engine):
    now = _now()
    with Session(engine) as s:
        paper = Paper(
            title="Test Paper", normalized_title="test paper",
            source_type="paper", topic_context="test",
            status="pending", queued_at=now,
        )
        topic = Topic(name="test topic", status="active", created_at=now, updated_at=now)
        s.add_all([paper, topic])
        s.flush()
        s.add(PaperTopic(paper_id=paper.id, topic_id=topic.id))
        s.commit()
    with pytest.raises(IntegrityError):
        with Session(engine) as s:
            paper = s.query(Paper).first()
            topic = s.query(Topic).first()
            s.add(PaperTopic(paper_id=paper.id, topic_id=topic.id))
            s.commit()
