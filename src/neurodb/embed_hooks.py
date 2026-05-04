"""Post-write hooks: sync DB records into the vector store after ingest or tag operations."""
from datetime import datetime, timezone
import hashlib

from sqlalchemy import Engine, text

from neurodb.db import get_session
from neurodb.schema import DatasetEmbeddingState
from neurodb.vector_store import VectorStore
from neurodb.vector_store import _dataset_text


def _dataset_content_hash(title: str, description: str | None, modality: str | None) -> str:
    text_value = _dataset_text(title, description, modality)
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()


def embed_source_datasets(engine: Engine, vector_store: VectorStore, source: str) -> int:
    """Embed changed datasets for a source from v_all_datasets. Returns count embedded."""
    with get_session(engine) as session:
        rows = session.execute(
            text("SELECT source, source_id, title, description, modality FROM v_all_datasets WHERE source = :src"),
            {"src": source},
        ).fetchall()
        existing_rows = session.execute(
            text(
                "SELECT source_id, content_hash, embedder_model "
                "FROM dataset_embedding_state WHERE source = :src"
            ),
            {"src": source},
        ).fetchall()

        existing = {
            row.source_id: (row.content_hash, row.embedder_model)
            for row in existing_rows
        }
        embedded_count = 0
        embedder_model = vector_store.dataset_embedding_version
        now = datetime.now(timezone.utc).isoformat()

        for row in rows:
            title = row.title or ""
            content_hash = _dataset_content_hash(title, row.description, row.modality)
            current_state = existing.get(row.source_id)
            if current_state == (content_hash, embedder_model):
                continue

            vector_store.upsert_dataset(
                source=row.source,
                source_id=row.source_id,
                title=title,
                description=row.description,
                modality=row.modality,
            )

            state = session.execute(
                text(
                    "SELECT id FROM dataset_embedding_state "
                    "WHERE source = :src AND source_id = :source_id"
                ),
                {"src": row.source, "source_id": row.source_id},
            ).fetchone()
            if state is None:
                session.add(DatasetEmbeddingState(
                    source=row.source,
                    source_id=row.source_id,
                    content_hash=content_hash,
                    embedder_model=embedder_model,
                    embedded_at=now,
                ))
            else:
                session.execute(
                    text(
                        "UPDATE dataset_embedding_state "
                        "SET content_hash = :content_hash, "
                        "embedder_model = :embedder_model, "
                        "embedded_at = :embedded_at "
                        "WHERE id = :id"
                    ),
                    {
                        "id": state.id,
                        "content_hash": content_hash,
                        "embedder_model": embedder_model,
                        "embedded_at": now,
                    },
                )
            embedded_count += 1

    return embedded_count


def embed_note(vector_store: VectorStore, tag_id: int, source: str, source_id: str,
               concept_tag: str, section_ref: str | None, note_text: str | None) -> None:
    vector_store.upsert_note(tag_id, source, source_id, concept_tag, section_ref, note_text)


def remove_note(vector_store: VectorStore, tag_id: int) -> None:
    vector_store.delete_note(tag_id)
