import uuid

import chromadb

from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Chunk


class _StubEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] if "hippocampus" in t else [0.0, 1.0] for t in texts]


def _store():
    return ChunkStore(
        client=chromadb.EphemeralClient(),
        embedder=_StubEmbedder(),
        collection_name=f"chunks_{uuid.uuid4().hex}",
    )


def _chunks():
    return [
        Chunk(0, "the hippocampus consolidates memory", "Intro", 0, 35),
        Chunk(1, "unrelated cerebellum text", "Methods", 36, 61),
    ]


def test_add_and_search_returns_provenance():
    store = _store()
    store.add_chunks(paper_id=5, title="T", year=2024, currency_status="current",
                     text_source="jats", chunks=_chunks())
    hits = store.search("hippocampus", n=1, min_score=0.0)
    assert hits[0]["text"].startswith("the hippocampus")
    assert hits[0]["section"] == "Intro"
    assert hits[0]["source_id"] == 5
    assert hits[0]["char_start"] == 0


def test_below_threshold_returns_empty():
    store = _store()
    store.add_chunks(paper_id=5, title="T", year=2024, currency_status="current",
                     text_source="jats", chunks=_chunks())
    assert store.search("hippocampus", n=1, min_score=2.0) == []


def test_reacquire_is_idempotent():
    store = _store()
    for _ in range(2):
        store.delete_paper(5)
        store.add_chunks(paper_id=5, title="T", year=2024, currency_status="current",
                         text_source="jats", chunks=_chunks())
    hits = store.search("hippocampus", n=10, min_score=0.0)
    assert len([h for h in hits if h["source_id"] == 5]) == 1
