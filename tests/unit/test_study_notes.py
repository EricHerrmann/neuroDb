import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, DatasetIndex, IngestRun, Paper, StudyNote
from neurodb.db.grouping_store import get_or_create_grouping, link_grouping
from neurodb.study import tag_dataset, list_tags, search_tags, delete_tag


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def full_engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def test_schema_includes_study_notes_table():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    inspector = inspect(engine)
    assert "study_notes" in inspector.get_table_names()


def test_study_note_saves_required_fields():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="dandi", source_id="000003", run_id=run.id)
        session.add(idx)
        session.flush()
        note = StudyNote(
            index_id=idx.id,
            concept_tag="primary visual cortex",
            tagged_at="2026-04-24T00:00:00+00:00",
        )
        session.add(note)
        session.commit()
        result = session.query(StudyNote).one()
        assert result.concept_tag == "primary visual cortex"
        assert result.section_ref is None
        assert result.note_text is None
        assert result.index_id == idx.id


def test_study_note_saves_optional_fields():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        session.add(idx)
        session.flush()
        note = StudyNote(
            index_id=idx.id,
            concept_tag="retinotopic mapping",
            section_ref="Augustine Ch13 p.312",
            note_text="V1 topographic organization matches discussion",
            tagged_at="2026-04-24T00:00:00+00:00",
        )
        session.add(note)
        session.commit()
        result = session.query(StudyNote).one()
        assert result.section_ref == "Augustine Ch13 p.312"
        assert result.note_text == "V1 topographic organization matches discussion"


def test_study_note_rejects_missing_index_id():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(IntegrityError):
            session.add(StudyNote(
                concept_tag="orphan tag",
                tagged_at="2026-04-24T00:00:00+00:00",
            ))
            session.commit()


def test_study_note_rejects_missing_tagged_at():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="dandi", source_id="000003", run_id=run.id)
        session.add(idx)
        session.flush()
        with pytest.raises(IntegrityError):
            session.add(StudyNote(
                index_id=idx.id,
                concept_tag="test concept",
            ))
            session.commit()


def test_tag_dataset_creates_study_note():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="dandi", source_id="000003", run_id=run.id)
        session.add(idx)
        session.flush()
        note = tag_dataset(session, "dandi", "000003", "hippocampus", section_ref="Augustine Ch24")
        session.commit()
        assert note is not None
        assert note.concept_tag == "hippocampus"
        assert note.section_ref == "Augustine Ch24"
        assert note.note_text is None


def test_tag_dataset_returns_none_for_unknown_dataset():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        note = tag_dataset(session, "dandi", "does-not-exist", "hippocampus")
    assert note is None


def _engine_with_two_tags():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx1 = DatasetIndex(source="dandi", source_id="000003", run_id=run.id)
        idx2 = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        session.add_all([idx1, idx2])
        session.flush()
        session.add(StudyNote(
            index_id=idx1.id,
            concept_tag="primary visual cortex",
            section_ref="Augustine Ch13",
            note_text="V1 electrode recordings",
            tagged_at="2026-04-24T00:00:00+00:00",
        ))
        session.add(StudyNote(
            index_id=idx2.id,
            concept_tag="auditory cortex",
            tagged_at="2026-04-23T00:00:00+00:00",
        ))
        session.commit()
    return engine


def test_list_tags_returns_all():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = list_tags(session)
    assert len(results) == 2
    concepts = {r["concept_tag"] for r in results}
    assert concepts == {"primary visual cortex", "auditory cortex"}


def test_list_tags_filters_by_concept():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = list_tags(session, concept="visual")
    assert len(results) == 1
    assert results[0]["concept_tag"] == "primary visual cortex"


def test_list_tags_filters_by_source():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = list_tags(session, source="openneuro")
    assert len(results) == 1
    assert results[0]["source_id"] == "ds001"


def test_search_tags_matches_concept():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = search_tags(session, "visual")
    assert len(results) == 1
    assert results[0]["concept_tag"] == "primary visual cortex"


def test_search_tags_matches_note_text():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = search_tags(session, "electrode")
    assert len(results) == 1
    assert results[0]["note_text"] == "V1 electrode recordings"


def test_search_tags_no_match_returns_empty():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = search_tags(session, "somatosensory")
    assert results == []


def test_list_tags_includes_id():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = list_tags(session)
    assert all("id" in r for r in results)
    assert all(isinstance(r["id"], int) for r in results)


def test_delete_tag_removes_row():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        tags = list_tags(session)
    assert len(tags) == 2
    tag_id = tags[0]["id"]
    with Session(engine) as session:
        deleted = delete_tag(session, tag_id)
        session.commit()
    assert deleted is True
    with Session(engine) as session:
        remaining = list_tags(session)
    assert len(remaining) == 1
    assert remaining[0]["id"] != tag_id


def test_delete_tag_unknown_id_returns_false():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        result = delete_tag(session, 999999)
        session.commit()
    assert result is False


# --- LOG-059: outer join tests for topic/concept/paper-anchored notes ---

def test_list_tags_includes_topic_anchored_note(full_engine):
    with Session(full_engine) as s:
        grouping = get_or_create_grouping(s, "topic", "LTP")
        note = StudyNote(topic_id=1, concept_tag="potentiation", tagged_at=_now())
        s.add(note)
        s.flush()
        link_grouping(s, grouping.id, "study_note", note.id, status="confirmed")
        s.commit()

    with Session(full_engine) as s:
        results = list_tags(s)
    assert len(results) == 1
    assert results[0]["source"] == "topic"
    assert results[0]["source_id"] == "LTP"
    assert results[0]["concept_tag"] == "potentiation"


def test_list_tags_includes_concept_anchored_note(full_engine):
    with Session(full_engine) as s:
        grouping = get_or_create_grouping(s, "concept", "synaptic pruning")
        note = StudyNote(concept_id=1, concept_tag="pruning", tagged_at=_now())
        s.add(note)
        s.flush()
        link_grouping(s, grouping.id, "study_note", note.id, status="confirmed")
        s.commit()

    with Session(full_engine) as s:
        results = list_tags(s)
    assert len(results) == 1
    assert results[0]["source"] == "concept"
    assert results[0]["source_id"] == "synaptic pruning"


def test_list_tags_includes_paper_anchored_note(full_engine):
    with Session(full_engine) as s:
        paper = Paper(title="LTP Review", normalized_title="ltp review",
                      doi="10.test/ltp", source_type="paper",
                      topic_context="plasticity", status="pending", queued_at=_now())
        s.add(paper)
        s.flush()
        s.add(StudyNote(paper_id=paper.id, concept_tag="LTP", tagged_at=_now()))
        s.commit()

    with Session(full_engine) as s:
        results = list_tags(s)
    assert len(results) == 1
    assert results[0]["source"] == "paper"
    assert results[0]["source_id"] == "10.test/ltp"


def test_list_tags_source_filter_excludes_topic_notes(full_engine):
    with Session(full_engine) as s:
        run = IngestRun(source="openneuro", run_at=_now(), version="1")
        s.add(run)
        s.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds1", run_id=run.id)
        s.add(idx)
        s.flush()
        grouping = get_or_create_grouping(s, "topic", "LTP")
        s.add(StudyNote(index_id=idx.id, concept_tag="ds_note", tagged_at=_now()))
        note = StudyNote(topic_id=1, concept_tag="topic_note", tagged_at=_now())
        s.add(note)
        s.flush()
        link_grouping(s, grouping.id, "study_note", note.id, status="confirmed")
        s.commit()

    with Session(full_engine) as s:
        results = list_tags(s, source="openneuro")
    assert len(results) == 1
    assert results[0]["concept_tag"] == "ds_note"


def test_search_tags_matches_topic_anchored_note(full_engine):
    with Session(full_engine) as s:
        grouping = get_or_create_grouping(s, "topic", "plasticity")
        note = StudyNote(
            topic_id=1,
            concept_tag="LTP",
            note_text="long-term potentiation",
            tagged_at=_now(),
        )
        s.add(note)
        s.flush()
        link_grouping(s, grouping.id, "study_note", note.id, status="confirmed")
        s.commit()

    with Session(full_engine) as s:
        results = search_tags(s, "potentiation")
    assert len(results) == 1
    assert results[0]["source"] == "topic"
    assert results[0]["source_id"] == "plasticity"
