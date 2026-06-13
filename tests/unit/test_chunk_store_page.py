import uuid, chromadb
from neurodb.chunking import Chunk
from neurodb.chunk_store import ChunkStore


class _Emb:
    def embed(self, texts): return [[0.1, 0.2, 0.3] for _ in texts]


def test_search_returns_page():
    store = ChunkStore(client=chromadb.EphemeralClient(), embedder=_Emb(),
                       collection_name=f"t_{uuid.uuid4().hex}")
    store.add_chunks(paper_id=1, title="P", year=2020, currency_status="current",
                     text_source="pdf_pymupdf",
                     chunks=[Chunk(0, "memory consolidation", "Intro", 0, 20, page=4)])
    hits = store.search("memory consolidation", n=1)
    assert hits[0]["page"] == 4


def test_search_page_none_when_absent():
    store = ChunkStore(client=chromadb.EphemeralClient(), embedder=_Emb(),
                       collection_name=f"t_{uuid.uuid4().hex}")
    store.add_chunks(paper_id=2, title="P", year=2020, currency_status="current",
                     text_source="jats",
                     chunks=[Chunk(0, "structured text here", "Intro", 0, 20)])
    hits = store.search("structured text", n=1)
    assert hits[0]["page"] is None
