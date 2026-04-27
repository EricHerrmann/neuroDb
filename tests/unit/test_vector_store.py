"""Unit tests for VectorStore — uses ephemeral ChromaDB and a stub Embedder."""
import chromadb
import pytest

from neurodb.vector_store import VectorStore, _dataset_text, _note_text


class _StubEmbedder:
    """Returns deterministic 4-dim embeddings keyed on text content."""
    _VECS = {
        "hippocampus": [1.0, 0.0, 0.0, 0.0],
        "visual cortex": [0.0, 1.0, 0.0, 0.0],
        "default": [0.0, 0.0, 1.0, 0.0],
    }

    def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            for key, vec in self._VECS.items():
                if key in text.lower():
                    results.append(vec)
                    break
            else:
                results.append(self._VECS["default"])
        return results


@pytest.fixture
def store():
    client = chromadb.EphemeralClient()
    return VectorStore(client=client, embedder=_StubEmbedder())


def test_upsert_dataset_adds_document(store):
    store.upsert_dataset("dandi", "000003", "Hippocampus Place Cells", None, "icephys")
    results = store.search("hippocampus", n_results=5)
    ids = [r["id"] for r in results]
    assert "dataset:dandi:000003" in ids


def test_upsert_note_adds_document(store):
    store.upsert_note(42, "dandi", "000003", "hippocampus spatial navigation", "Augustine Ch24", None)
    results = store.search("hippocampus", n_results=5)
    ids = [r["id"] for r in results]
    assert "note:42" in ids


def test_upsert_is_idempotent(store):
    store.upsert_dataset("openneuro", "ds001", "V1 Study", None, "fMRI")
    store.upsert_dataset("openneuro", "ds001", "V1 Study", None, "fMRI")
    results = store.search("visual", n_results=10)
    matching = [r for r in results if r["id"] == "dataset:openneuro:ds001"]
    assert len(matching) == 1


def test_delete_note_removes_document(store):
    store.upsert_note(7, "openneuro", "ds001", "visual cortex retinotopy", None, None)
    store.delete_note(7)
    results = store.search("visual cortex", n_results=10)
    ids = [r["id"] for r in results]
    assert "note:7" not in ids


def test_search_returns_metadata(store):
    store.upsert_dataset("dandi", "000003", "Hippocampus Study", "Place cells", "icephys")
    results = store.search("hippocampus", n_results=5)
    match = next(r for r in results if r["id"] == "dataset:dandi:000003")
    assert match["metadata"]["source"] == "dandi"
    assert match["metadata"]["source_id"] == "000003"
    assert match["metadata"]["type"] == "dataset"


def test_dataset_text_combines_fields():
    assert _dataset_text("V1 Study", "Retinotopic mapping", "fMRI") == "V1 Study [SEP] fMRI [SEP] Retinotopic mapping"
    assert _dataset_text("V1 Study", None, None) == "V1 Study"


def test_note_text_combines_fields():
    assert _note_text("hippocampus", "Augustine Ch24", "place cells") == "hippocampus [SEP] Augustine Ch24 [SEP] place cells"
    assert _note_text("hippocampus", None, None) == "hippocampus"
