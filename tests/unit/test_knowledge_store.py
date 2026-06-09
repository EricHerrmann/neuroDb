import uuid

import chromadb

from neurodb.knowledge_store import KnowledgeLibraryStore


class _StubEmbedder:
    def embed(self, texts):
        embeddings = []
        for text in texts:
            base = 1.0 if "hippocampus" in text.lower() or "ltp" in text.lower() else 0.0
            embeddings.append([base, 1.0 - base, 0.1, 0.2])
        return embeddings


def _store():
    client = chromadb.EphemeralClient()
    return KnowledgeLibraryStore(
        client=client,
        embedder=_StubEmbedder(),
        collection_name=f"test_knowledge_{uuid.uuid4().hex}",
    )


def test_add_summary_returns_chroma_id():
    store = _store()
    doc_id = store.add_summary(
        source_id=1,
        title="LTP Review",
        doi="10.1234/ltp",
        topic_context="synaptic plasticity",
        summary="Long-term potentiation in hippocampus supports memory.",
    )
    assert doc_id == "knowledge_source:1"


def test_search_empty_collection_returns_empty():
    assert _store().search("hippocampus") == []


def test_add_and_search_summary_round_trip():
    store = _store()
    store.add_summary(
        source_id=1,
        title="LTP Review",
        doi="10.1234/ltp",
        topic_context="synaptic plasticity",
        summary="Long-term potentiation in hippocampus supports memory.",
    )
    results = store.search("hippocampus LTP", n=3)
    assert len(results) == 1
    assert results[0]["id"] == "knowledge_source:1"
    assert "Long-term potentiation" in results[0]["document"]
    assert results[0]["metadata"]["title"] == "LTP Review"


def test_search_limits_results():
    store = _store()
    for source_id in range(3):
        store.add_summary(
            source_id=source_id,
            title=f"Source {source_id}",
            doi=None,
            topic_context="plasticity",
            summary=f"Hippocampus LTP source {source_id}",
        )
    assert len(store.search("hippocampus", n=2)) == 2


def test_add_summary_upserts_existing_source_id():
    store = _store()
    store.add_summary(1, "Old", None, "topic", "Old hippocampus summary")
    store.add_summary(1, "New", None, "topic", "New hippocampus summary")
    results = store.search("hippocampus", n=5)
    assert len(results) == 1
    assert results[0]["metadata"]["title"] == "New"


def test_add_summary_records_tier_year_currency():
    store = _store()
    store.add_summary(
        source_id=7, title="T", doi=None, topic_context="memory",
        summary="s", data_tier="abstract", year=2024, currency_status="current",
    )
    results = store.search("memory", n=1)
    meta = results[0]["metadata"]
    assert meta["data_tier"] == "abstract"
    assert meta["year"] == "2024"
    assert meta["currency_status"] == "current"

