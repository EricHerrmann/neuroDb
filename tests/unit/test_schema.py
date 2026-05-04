import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neurodb.schema import (
    CrossRef,
    DatasetEmbeddingState,
    DatasetIndex,
    ImportQueue,
    IngestRun,
    LearningSource,
    QualityEvent,
    SourceSuggestion,
    Subject,
)


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


def test_learning_source_tablename():
    assert LearningSource.__tablename__ == "learning_sources"


def test_import_queue_tablename():
    assert ImportQueue.__tablename__ == "import_queue"


def test_source_suggestion_tablename():
    assert SourceSuggestion.__tablename__ == "source_suggestions"


def test_learning_source_has_metadata_json_column():
    cols = {c.key for c in LearningSource.__table__.columns}
    assert "metadata_json" in cols
    assert "content_json" in cols
    assert "source_type" in cols
    assert "source_key" in cols


def test_import_queue_has_open_status_column():
    cols = {c.key for c in ImportQueue.__table__.columns}
    assert "status" in cols
    assert "metadata_json" in cols
    assert "chapter_ref" in cols


def test_source_suggestion_has_suggestion_type_column():
    cols = {c.key for c in SourceSuggestion.__table__.columns}
    assert "suggestion_type" in cols
    assert "metadata_json" in cols


def test_dataset_embedding_state_has_hash_and_model_columns():
    cols = {c.key for c in DatasetEmbeddingState.__table__.columns}
    assert "source" in cols
    assert "source_id" in cols
    assert "content_hash" in cols
    assert "embedder_model" in cols
