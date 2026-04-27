"""Post-write hooks: sync DB records into the vector store after ingest or tag operations."""
from sqlalchemy import Engine, text

from neurodb.db import get_session
from neurodb.vector_store import VectorStore


def embed_source_datasets(engine: Engine, vector_store: VectorStore, source: str) -> int:
    """Embed all datasets for a source from v_all_datasets. Returns count embedded."""
    with get_session(engine) as session:
        rows = session.execute(
            text("SELECT source, source_id, title, description, modality FROM v_all_datasets WHERE source = :src"),
            {"src": source},
        ).fetchall()
    for row in rows:
        vector_store.upsert_dataset(
            source=row.source,
            source_id=row.source_id,
            title=row.title or "",
            description=row.description,
            modality=row.modality,
        )
    return len(rows)


def embed_note(vector_store: VectorStore, tag_id: int, source: str, source_id: str,
               concept_tag: str, section_ref: str | None, note_text: str | None) -> None:
    vector_store.upsert_note(tag_id, source, source_id, concept_tag, section_ref, note_text)


def remove_note(vector_store: VectorStore, tag_id: int) -> None:
    vector_store.delete_note(tag_id)
