from sqlalchemy import create_engine, text

from neurodb.embed_hooks import _dataset_content_hash, embed_source_datasets
from neurodb.schema import DatasetEmbeddingState


class _StubVectorStore:
    def __init__(self, version: str = "stub-model") -> None:
        self.dataset_embedding_version = version
        self.calls: list[dict] = []

    def upsert_dataset(self, source: str, source_id: str, title: str, description: str | None, modality: str | None) -> None:
        self.calls.append({
            "source": source,
            "source_id": source_id,
            "title": title,
            "description": description,
            "modality": modality,
        })


def _engine_with_dataset_view():
    engine = create_engine("sqlite:///:memory:")
    DatasetEmbeddingState.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE dataset_rows (
                source TEXT,
                source_id TEXT,
                title TEXT,
                description TEXT,
                modality TEXT
            )
        """))
        conn.execute(text("""
            CREATE VIEW v_all_datasets AS
            SELECT source, source_id, title, description, modality FROM dataset_rows
        """))
    return engine


def test_dataset_content_hash_changes_when_input_changes():
    old_hash = _dataset_content_hash("V1 Study", "Retinotopy", "fMRI")
    new_hash = _dataset_content_hash("V1 Study", "Orientation columns", "fMRI")
    assert old_hash != new_hash


def test_embed_source_datasets_skips_unchanged_rows():
    engine = _engine_with_dataset_view()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO dataset_rows (source, source_id, title, description, modality)
            VALUES
            ('openneuro', 'ds001', 'V1 Study', 'Retinotopy', 'fMRI'),
            ('openneuro', 'ds002', 'M1 Study', 'Motor cortex', 'EEG')
        """))

    vs = _StubVectorStore()
    assert embed_source_datasets(engine, vs, "openneuro") == 2
    assert len(vs.calls) == 2

    vs.calls.clear()
    assert embed_source_datasets(engine, vs, "openneuro") == 0
    assert vs.calls == []


def test_embed_source_datasets_reembeds_changed_rows_only():
    engine = _engine_with_dataset_view()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO dataset_rows (source, source_id, title, description, modality)
            VALUES
            ('openneuro', 'ds001', 'V1 Study', 'Retinotopy', 'fMRI'),
            ('openneuro', 'ds002', 'M1 Study', 'Motor cortex', 'EEG')
        """))

    vs = _StubVectorStore()
    assert embed_source_datasets(engine, vs, "openneuro") == 2

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE dataset_rows
            SET description = 'Orientation columns'
            WHERE source = 'openneuro' AND source_id = 'ds001'
        """))

    vs.calls.clear()
    assert embed_source_datasets(engine, vs, "openneuro") == 1
    assert [call["source_id"] for call in vs.calls] == ["ds001"]


def test_embed_source_datasets_reembeds_when_model_changes():
    engine = _engine_with_dataset_view()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO dataset_rows (source, source_id, title, description, modality)
            VALUES ('openneuro', 'ds001', 'V1 Study', 'Retinotopy', 'fMRI')
        """))

    vs1 = _StubVectorStore(version="model-a")
    assert embed_source_datasets(engine, vs1, "openneuro") == 1

    vs2 = _StubVectorStore(version="model-b")
    assert embed_source_datasets(engine, vs2, "openneuro") == 1
