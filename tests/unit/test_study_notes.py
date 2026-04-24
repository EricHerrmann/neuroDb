import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neurodb.schema import DatasetIndex, IngestRun, StudyNote


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
        with pytest.raises((IntegrityError, Exception)):
            session.add(StudyNote(
                index_id=idx.id,
                concept_tag="test concept",
            ))
            session.commit()
