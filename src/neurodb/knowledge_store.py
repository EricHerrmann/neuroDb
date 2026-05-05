"""ChromaDB-backed Knowledge Library for approved source summaries."""
import chromadb

COLLECTION_NAME = "knowledge_library"


class KnowledgeLibraryStore:
    """Semantic index of approved Neuro-Tutor source summaries."""

    def __init__(
        self,
        path: str | None = None,
        client: chromadb.ClientAPI | None = None,
        embedder=None,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        if client is not None:
            self._client = client
        elif path is not None:
            self._client = chromadb.PersistentClient(path=path)
        else:
            raise ValueError("Either path or client must be provided")
        self._embedder = embedder
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_summary(
        self,
        source_id: int,
        title: str,
        doi: str | None,
        topic_context: str,
        summary: str,
    ) -> str:
        """Add or replace an approved source summary and return the Chroma doc ID."""
        doc_id = f"knowledge_source:{source_id}"
        metadata = {
            "source_id": str(source_id),
            "title": title,
            "doi": doi or "",
            "topic_context": topic_context,
        }
        kwargs = {
            "ids": [doc_id],
            "documents": [summary],
            "metadatas": [metadata],
        }
        if self._embedder is not None:
            kwargs["embeddings"] = [self._embedder.embed([summary])[0]]
        self._collection.upsert(**kwargs)
        return doc_id

    def search(self, query: str, n: int = 5) -> list[dict]:
        """Return semantically similar approved summaries."""
        if not query:
            return []
        count = self._collection.count()
        if count == 0:
            return []
        actual_n = min(n, count)
        kwargs = {"n_results": actual_n}
        if self._embedder is not None:
            kwargs["query_embeddings"] = [self._embedder.embed([query])[0]]
        else:
            kwargs["query_texts"] = [query]
        results = self._collection.query(**kwargs)
        if not results["ids"]:
            return []
        return [
            {
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
            for i, doc_id in enumerate(results["ids"][0])
        ]

