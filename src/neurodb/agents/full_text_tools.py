"""Shared full-text quoting tools (registered on tutor + research agents)."""
from __future__ import annotations

import json

from neurodb.quote_verify import verify_quote

FULL_TEXT_TOOLS = [
    {
        "name": "search_full_text",
        "description": (
            "Search stored full text of acquired papers and return verbatim, "
            "provenance-anchored passages eligible for quoting. Returns "
            "{grounded: false} when nothing clears the relevance threshold — "
            "say so rather than inventing a quote."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to find in full text."},
                "n_results": {"type": "integer", "description": "Max passages."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "verify_quote",
        "description": (
            "Verify a verbatim quote against the stored full text of a source before "
            "presenting it. Returns {matched: true, ...provenance} or {matched: false}. "
            "A quote may be tagged [verified] ONLY after this returns matched=true."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The exact text to verify."},
                "source_id": {"type": "integer", "description": "The paper/source id."},
            },
            "required": ["text", "source_id"],
        },
    },
]

DEFAULT_MIN_SCORE = 0.25


def execute_search_full_text(chunk_store, inputs: dict, *, min_score: float = DEFAULT_MIN_SCORE) -> str:
    if chunk_store is None:
        return json.dumps({"grounded": False, "message": "Full-text store not available."})
    passages = chunk_store.search(
        inputs["query"], n=inputs.get("n_results", 5), min_score=min_score
    )
    if not passages:
        return json.dumps({
            "grounded": False,
            "message": "No grounded full-text support for that query.",
        })
    return json.dumps({"grounded": True, "passages": passages})


def execute_verify_quote(chunk_store, inputs: dict, *, min_score: float = 0.0) -> str:
    if chunk_store is None:
        return json.dumps({"matched": False, "message": "Full-text store not available."})
    source_id = int(inputs["source_id"])
    # pull this source's chunks back out of the store for exact matching
    passages = chunk_store.search(inputs["text"], n=20, min_score=-1.0)
    chunks = [p for p in passages if p["source_id"] == source_id]
    match = verify_quote(inputs["text"], chunks)
    return json.dumps(match or {"matched": False})
