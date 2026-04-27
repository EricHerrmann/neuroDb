import chromadb

COLLECTION_NAME = "neuro_research"


def _dataset_text(title: str, description: str | None, modality: str | None) -> str:
    parts = [title]
    if modality:
        parts.append(modality)
    if description:
        parts.append(description)
    return " [SEP] ".join(parts)


def _note_text(concept_tag: str, section_ref: str | None, note_text: str | None) -> str:
    parts = [concept_tag]
    if section_ref:
        parts.append(section_ref)
    if note_text:
        parts.append(note_text)
    return " [SEP] ".join(parts)


class VectorStore:
    def __init__(self, path: str | None = None, client: chromadb.ClientAPI | None = None, embedder=None):
        if client is not None:
            self._client = client
        elif path is not None:
            self._client = chromadb.PersistentClient(path=path)
        else:
            raise ValueError("Either path or client must be provided")
        self._embedder = embedder
        self._collection = self._client.get_or_create_collection(COLLECTION_NAME)

    def upsert_dataset(
        self,
        source: str,
        source_id: str,
        title: str,
        description: str | None,
        modality: str | None,
    ) -> None:
        text = _dataset_text(title, description, modality)
        doc_id = f"dataset:{source}:{source_id}"
        embedding = self._embedder.embed([text])[0]
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{"type": "dataset", "source": source, "source_id": source_id}],
        )

    def upsert_note(
        self,
        tag_id: int,
        source: str,
        source_id: str,
        concept_tag: str,
        section_ref: str | None,
        note_text: str | None,
    ) -> None:
        text = _note_text(concept_tag, section_ref, note_text)
        doc_id = f"note:{tag_id}"
        embedding = self._embedder.embed([text])[0]
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{"type": "note", "source": source, "source_id": source_id, "tag_id": tag_id}],
        )

    def delete_note(self, tag_id: int) -> None:
        self._collection.delete(ids=[f"note:{tag_id}"])

    def search(self, query: str, n_results: int = 10) -> list[dict]:
        count = self._collection.count()
        if count == 0:
            return []
        actual_n = min(n_results, count)
        embedding = self._embedder.embed([query])[0]
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=actual_n,
        )
        return [
            {
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
            for i, doc_id in enumerate(results["ids"][0])
        ]
