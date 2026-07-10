"""Tests for the explicit Knowledge-Library directive path (workstream 1)."""
from __future__ import annotations

import pytest

from neurodb.agents.library_directive import (
    detect_library_directive,
    library_prompt_block,
    library_search_event,
    run_library_search,
)


@pytest.mark.parametrize("message", [
    "Use the knowledge library to answer this",
    "who does the library say wrote that paper?",
    "search in the KB for hippocampus results",
    "Please look it up in the library.",
    "check the library first",
    "is that in my library?",
])
def test_detector_matches_directive_phrases(message):
    assert detect_library_directive(message) is True


@pytest.mark.parametrize("message", [
    "tell me about neural plasticity",
    "the librarian recommended a book",
    "python library imports are failing",
    "we visited many libraries in Boston",
    "",
])
def test_detector_rejects_near_misses(message):
    assert detect_library_directive(message) is False


class _StubChunkStore:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, query, n=5, min_score=0.0):
        self.calls.append({"query": query, "n": n, "min_score": min_score})
        return self.hits


class _StubKnowledgeStore:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, query, n=5):
        self.calls.append({"query": query, "n": n})
        return self.hits


_PASSAGE = {"chunk_id": "chunk:9:0", "text": "collective abilities emerge",
            "source_id": 9, "title": "Hopfield 1982", "section": "Abstract",
            "score": 0.9}
_SUMMARY = {"id": "knowledge_source:9", "document": "summary body",
            "metadata": {"title": "Hopfield 1982"}, "distance": 0.1}


def test_full_text_hit_skips_summary_fallback():
    chunk_store = _StubChunkStore([_PASSAGE])
    knowledge_store = _StubKnowledgeStore([_SUMMARY])
    result = run_library_search("q", chunk_store=chunk_store,
                                knowledge_store=knowledge_store)
    assert result["full_text_count"] == 1 and result["summary_count"] == 0
    assert knowledge_store.calls == []
    assert chunk_store.calls[0]["min_score"] == 0.25


def test_empty_full_text_falls_back_to_summaries():
    result = run_library_search("q", chunk_store=_StubChunkStore([]),
                                knowledge_store=_StubKnowledgeStore([_SUMMARY]))
    assert result["full_text_count"] == 0 and result["summary_count"] == 1


def test_missing_stores_yield_empty_result():
    result = run_library_search("q", chunk_store=None, knowledge_store=None)
    assert result["full_text_count"] == 0 and result["summary_count"] == 0


def test_prompt_block_carries_full_content_not_just_titles():
    block = library_prompt_block(run_library_search(
        "q", chunk_store=_StubChunkStore([_PASSAGE]),
        knowledge_store=_StubKnowledgeStore([])))
    assert "collective abilities emerge" in block  # passage body, not title-only
    assert "MUST ground" in block


def test_prompt_block_summary_section_carries_document_body():
    block = library_prompt_block(run_library_search(
        "q", chunk_store=_StubChunkStore([]),
        knowledge_store=_StubKnowledgeStore([_SUMMARY])))
    assert "summary body" in block


def test_prompt_block_empty_case_instructs_plain_statement():
    block = library_prompt_block(run_library_search(
        "q", chunk_store=_StubChunkStore([]),
        knowledge_store=_StubKnowledgeStore([])))
    assert "nothing" in block.lower()
    assert "searched" in block.lower()


def test_library_search_event_shape():
    event = library_search_event(run_library_search(
        "q", chunk_store=_StubChunkStore([_PASSAGE]),
        knowledge_store=_StubKnowledgeStore([])))
    assert event["type"] == "library_search"
    assert event["full_text_count"] == 1 and event["summary_count"] == 0
    assert "full-text passages: 1" in event["text"]
