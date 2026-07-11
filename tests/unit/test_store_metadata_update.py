"""Tests for metadata-only updates on the two Chroma stores (no re-embedding)."""
from __future__ import annotations

import uuid

import chromadb

from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Chunk
from neurodb.knowledge_store import KnowledgeLibraryStore


class _StubEmbedder:
    def __init__(self):
        self.embed_calls = 0

    def embed(self, texts):
        self.embed_calls += 1
        return [[0.1, 0.2, 0.3] for _ in texts]


def _chunk_store(embedder):
    return ChunkStore(client=chromadb.EphemeralClient(), embedder=embedder,
                      collection_name=f"ck_{uuid.uuid4().hex}")


def _knowledge_store(embedder):
    return KnowledgeLibraryStore(client=chromadb.EphemeralClient(), embedder=embedder,
                                 collection_name=f"kl_{uuid.uuid4().hex}")


def _seed_chunks(store, paper_id=9):
    store.add_chunks(
        paper_id=paper_id, title="Hopfield 1982", year=None,
        currency_status="current", text_source="pdf_pymupdf",
        chunks=[
            Chunk(chunk_index=0, text="alpha", section="Intro", char_start=0, char_end=5),
            Chunk(chunk_index=1, text="beta", section="Methods", char_start=5, char_end=9),
        ],
    )


def test_chunk_metadata_update_merges_and_counts():
    embedder = _StubEmbedder()
    store = _chunk_store(embedder)
    _seed_chunks(store)
    baseline_calls = embedder.embed_calls
    updated = store.update_paper_metadata(9, {"authors": "J. Hopfield", "year": "1982"})
    assert updated == 2
    assert embedder.embed_calls == baseline_calls  # metadata-only, no re-embed
    hits = store.search("alpha", n=5, min_score=-1.0)
    target = [h for h in hits if h["chunk_id"] == "chunk:9:0"][0]
    assert target["year"] == "1982"
    assert target["section"] == "Intro"  # untouched fields preserved


def test_chunk_metadata_update_missing_paper_returns_zero():
    assert _chunk_store(_StubEmbedder()).update_paper_metadata(123, {"a": "b"}) == 0


def test_summary_metadata_update_merges_without_reembedding():
    embedder = _StubEmbedder()
    store = _knowledge_store(embedder)
    store.add_summary(source_id=9, title="Hopfield 1982", doi=None,
                      topic_context="memory", summary="summary text",
                      data_tier="abstract")
    baseline_calls = embedder.embed_calls
    assert store.update_summary_metadata(
        9, {"data_tier": "full_text", "authors": "J. Hopfield"}) is True
    assert embedder.embed_calls == baseline_calls
    hit = store.search("summary text", n=1)[0]
    assert hit["metadata"]["data_tier"] == "full_text"
    assert hit["metadata"]["authors"] == "J. Hopfield"
    assert hit["metadata"]["title"] == "Hopfield 1982"  # untouched fields preserved


def test_summary_metadata_update_missing_doc_returns_false():
    assert _knowledge_store(_StubEmbedder()).update_summary_metadata(77, {}) is False
