"""Second Chroma collection holding quotable full-text chunks (Phase 2a)."""
from __future__ import annotations

import chromadb

from neurodb.chunking import Chunk

CHUNK_COLLECTION_NAME = "knowledge_chunks"


class ChunkStore:
    """Semantic index of full-text chunks; only full_text-tier papers live here."""

    def __init__(self, path=None, client=None, embedder=None,
                 collection_name: str = CHUNK_COLLECTION_NAME) -> None:
        if client is not None:
            self._client = client
        elif path is not None:
            self._client = chromadb.PersistentClient(path=path)
        else:
            raise ValueError("Either path or client must be provided")
        self._embedder = embedder
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"},
        )

    def _chunk_id(self, paper_id: int, chunk_index: int) -> str:
        return f"chunk:{paper_id}:{chunk_index}"

    def add_chunks(self, *, paper_id: int, title: str, year: int | None,
                   currency_status: str, text_source: str, chunks: list[Chunk]) -> list[str]:
        if not chunks:
            return []
        ids = [self._chunk_id(paper_id, c.chunk_index) for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "source_id": str(paper_id),
                "paper_id": str(paper_id),
                "chunk_index": c.chunk_index,
                "section": c.section or "",
                "char_start": c.char_start if c.char_start is not None else -1,
                "char_end": c.char_end if c.char_end is not None else -1,
                "text_source": text_source,
                "title": title,
                "year": str(year) if year else "",
                "currency_status": currency_status,
                "data_tier": "full_text",
                "page": str(c.page) if c.page is not None else "",
            }
            for c in chunks
        ]
        kwargs = {"ids": ids, "documents": documents, "metadatas": metadatas}
        if self._embedder is not None:
            kwargs["embeddings"] = self._embedder.embed(documents)
        self._collection.upsert(**kwargs)
        return ids

    def delete_paper(self, paper_id: int) -> None:
        try:
            self._collection.delete(where={"paper_id": str(paper_id)})
        except Exception:
            pass

    def update_paper_metadata(self, paper_id: int, metadata: dict) -> int:
        """Merge metadata into every chunk of a paper without re-embedding."""
        existing = self._collection.get(where={"paper_id": str(paper_id)})
        ids = existing.get("ids") or []
        if not ids:
            return 0
        merged = [{**(old or {}), **metadata} for old in existing["metadatas"]]
        self._collection.update(ids=ids, metadatas=merged)
        return len(ids)

    def search(self, query: str, n: int = 5, min_score: float = 0.0) -> list[dict]:
        if not query:
            return []
        count = self._collection.count()
        if count == 0:
            return []
        kwargs = {"n_results": min(n, count)}
        if self._embedder is not None:
            kwargs["query_embeddings"] = [self._embedder.embed([query])[0]]
        else:
            kwargs["query_texts"] = [query]
        res = self._collection.query(**kwargs)
        if not res["ids"]:
            return []
        out = []
        for i, doc_id in enumerate(res["ids"][0]):
            meta = res["metadatas"][0][i]
            distance = res["distances"][0][i]
            score = 1.0 - distance  # cosine distance → similarity
            if score <= min_score:
                continue
            out.append({
                "chunk_id": doc_id,
                "text": res["documents"][0][i],
                "source_id": int(meta.get("source_id") or 0),
                "title": meta.get("title", ""),
                "section": meta.get("section") or None,
                "char_start": meta.get("char_start"),
                "char_end": meta.get("char_end"),
                "text_source": meta.get("text_source", ""),
                "year": meta.get("year") or "",
                "currency_status": meta.get("currency_status", "current"),
                "page": int(meta["page"]) if meta.get("page") else None,
                "score": score,
            })
        return out
