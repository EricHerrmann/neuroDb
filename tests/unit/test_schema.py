import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neurodb.schema import CrossRef, DatasetIndex, IngestRun, QualityEvent, Subject


def test_schema_creates_core_tables():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    assert "datasets_index" in table_names
    assert "subjects" in table_names
    assert "ingest_runs" in table_names
    assert "cross_refs" in table_names
    assert "quality_events" in table_names


def test_dataset_index_and_subject_linkage():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-04-11T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        session.add(idx)
        session.flush()
        subject = Subject(index_id=idx.id, source_subject_id="sub-01", age=25.0, sex="M")
        session.add(subject)
        session.commit()
        assert session.query(DatasetIndex).count() == 1
        assert session.query(Subject).count() == 1
        assert session.query(CrossRef).count() == 0
        assert session.query(QualityEvent).count() == 0


def test_dataset_index_rejects_duplicate_source_id():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-04-11T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        session.add(DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id))
        session.commit()
    with Session(engine) as session:
        run2 = session.query(IngestRun).first()
        session.add(DatasetIndex(source="openneuro", source_id="ds001", run_id=run2.id))
        with pytest.raises(IntegrityError):
            session.commit()
