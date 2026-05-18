import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import (
    Base, Concept, DatasetIndex, IngestRun, Paper, StudyNote, Topic,
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


def _make_dataset(session):
    run = IngestRun(source="test", run_at=_now(), version="1")
    session.add(run)
    session.flush()
    idx = DatasetIndex(source="test", source_id="ds1", run_id=run.id)
    session.add(idx)
    session.flush()
    return idx


def test_study_note_accepts_index_id_anchor(engine):
    with Session(engine) as s:
        idx = _make_dataset(s)
        s.add(StudyNote(index_id=idx.id, concept_tag="plasticity", tagged_at=_now()))
        s.commit()


def test_study_note_accepts_topic_id_anchor(engine):
    with Session(engine) as s:
        topic = Topic(name="hippocampal plasticity", status="active",
                      created_at=_now(), updated_at=_now())
        s.add(topic)
        s.flush()
        s.add(StudyNote(topic_id=topic.id, concept_tag="LTP", tagged_at=_now()))
        s.commit()


def test_study_note_accepts_concept_id_anchor(engine):
    with Session(engine) as s:
        concept = Concept(name="synaptic pruning", status="active",
                          created_at=_now(), updated_at=_now())
        s.add(concept)
        s.flush()
        s.add(StudyNote(concept_id=concept.id, concept_tag="pruning", tagged_at=_now()))
        s.commit()


def test_study_note_accepts_paper_id_anchor(engine):
    with Session(engine) as s:
        paper = Paper(title="LTP Review", normalized_title="ltp review",
                      source_type="paper", topic_context="plasticity",
                      status="pending", queued_at=_now())
        s.add(paper)
        s.flush()
        s.add(StudyNote(paper_id=paper.id, concept_tag="LTP", tagged_at=_now()))
        s.commit()


def test_study_note_rejects_all_null_anchors(engine):
    with pytest.raises(Exception):
        with Session(engine) as s:
            s.add(StudyNote(concept_tag="LTP", tagged_at=_now()))
            s.commit()


def test_study_note_index_id_is_nullable(engine):
    cols = {c["name"]: c for c in __import__("sqlalchemy", fromlist=["inspect"]).inspect(engine).get_columns("study_notes")}
    assert cols["index_id"]["nullable"] is True
