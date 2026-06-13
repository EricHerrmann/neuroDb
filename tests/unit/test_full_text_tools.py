import json
import uuid

import chromadb

from neurodb.agents.full_text_tools import (
    FULL_TEXT_TOOLS,
    execute_search_full_text,
    execute_verify_quote,
)
from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Chunk


class _StubEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] if "hippocampus" in t else [0.0, 1.0] for t in texts]


def _store():
    s = ChunkStore(client=chromadb.EphemeralClient(), embedder=_StubEmbedder(),
                   collection_name=f"chunks_{uuid.uuid4().hex}")
    s.add_chunks(paper_id=9, title="Ripples", year=2024, currency_status="current",
                 text_source="jats",
                 chunks=[Chunk(0, "the hippocampus consolidates memory", "Intro", 0, 35)])
    return s


def test_tool_names_present():
    names = {t["name"] for t in FULL_TEXT_TOOLS}
    assert names == {"search_full_text", "verify_quote"}


def test_search_returns_grounded_passage():
    out = json.loads(execute_search_full_text(_store(), {"query": "hippocampus"}, min_score=0.0))
    assert out["grounded"] is True
    assert out["passages"][0]["section"] == "Intro"
    assert "page" in out["passages"][0]


def test_search_returns_page_in_passage():
    s = ChunkStore(client=chromadb.EphemeralClient(), embedder=_StubEmbedder(),
                   collection_name=f"chunks_{uuid.uuid4().hex}")
    s.add_chunks(paper_id=42, title="PDFPaper", year=2023, currency_status="current",
                 text_source="pdf_pymupdf",
                 chunks=[Chunk(0, "the hippocampus consolidates memory", "Intro", 0, 35, page=7)])
    out = json.loads(execute_search_full_text(s, {"query": "hippocampus"}, min_score=0.0))
    assert out["grounded"] is True
    assert out["passages"][0]["page"] == 7


def test_search_below_threshold_is_honest_absence():
    out = json.loads(execute_search_full_text(_store(), {"query": "hippocampus"}, min_score=2.0))
    assert out["grounded"] is False


def test_verify_quote_matches_stored_chunk():
    out = json.loads(execute_verify_quote(_store(), {"text": "hippocampus consolidates", "source_id": 9}))
    assert out["matched"] is True
