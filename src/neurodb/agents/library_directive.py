"""Deterministic Knowledge-Library search on explicit user request (workstream 1).

The orchestrator (chat route) — not the model — runs the search on flagged turns
and injects full-content results as an authoritative block. Provider-independent
by construction: no reliance on tool_choice forcing.
"""
from __future__ import annotations

import re

from neurodb.agents.full_text_tools import DEFAULT_MIN_SCORE

# Extensible phrase list; matched case-insensitively on word boundaries.
# Non-deterministic edges are accepted (spec): tune by editing this list.
LIBRARY_DIRECTIVE_PHRASES = [
    "knowledge library",
    "the library",
    "my library",
    "our library",
    "this library",
    "in the kb",
    "the kb",
    "from the library",
    "check the library",
    "look it up in the library",
]

_PATTERNS = [
    re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
    for phrase in LIBRARY_DIRECTIVE_PHRASES
]


def detect_library_directive(message: str) -> bool:
    """True when the user explicitly invokes the Knowledge Library. Pure."""
    return any(pattern.search(message or "") for pattern in _PATTERNS)


def run_library_search(message: str, *, chunk_store, knowledge_store,
                       n: int = 5) -> dict:
    """Full-text search first; summary fallback only when full text is empty."""
    full_text: list[dict] = []
    summaries: list[dict] = []
    if chunk_store is not None:
        try:
            full_text = chunk_store.search(message, n=n, min_score=DEFAULT_MIN_SCORE)
        except Exception:
            full_text = []
    if not full_text and knowledge_store is not None:
        try:
            summaries = knowledge_store.search(message, n=n)
        except Exception:
            summaries = []
    return {
        "full_text": full_text,
        "summaries": summaries,
        "full_text_count": len(full_text),
        "summary_count": len(summaries),
    }


def library_prompt_block(result: dict) -> str:
    """Mandatory full-content injection block for a flagged turn."""
    lines = [
        "Knowledge Library results (deterministic search — the user explicitly "
        "asked for the Knowledge Library):",
        "You MUST ground your answer on these results, or state explicitly that "
        "the Knowledge Library was searched and the results were insufficient.",
    ]
    if result["full_text"]:
        lines += ["", f"Full-text passages ({result['full_text_count']}):"]
        for passage in result["full_text"]:
            section = f", {passage['section']}" if passage.get("section") else ""
            lines.append(f'- [{passage["title"]}{section}] "{passage["text"]}"')
    if result["summaries"]:
        lines += ["", f"Summary results ({result['summary_count']}):"]
        for summary in result["summaries"]:
            metadata = summary.get("metadata") or {}
            title = metadata.get("title") or summary.get("id")
            authors = metadata.get("authors") or ""
            byline = f" (authors: {authors})" if authors else ""
            lines.append(f"- [{title}{byline}] {summary.get('document', '')}")
    if not result["full_text"] and not result["summaries"]:
        lines += [
            "",
            "The Knowledge Library was searched for this request and returned "
            "nothing relevant. State plainly that the library was searched and had "
            "nothing relevant; do not imply library support and do not present "
            "training knowledge as if it came from the library.",
        ]
    return "\n".join(lines)


def library_search_event(result: dict) -> dict:
    """SSE event making the deterministic search visible in the UI."""
    return {
        "type": "library_search",
        "full_text_count": result["full_text_count"],
        "summary_count": result["summary_count"],
        "text": (
            "Searched Knowledge Library — full-text passages: "
            f"{result['full_text_count']}, summaries: {result['summary_count']}"
        ),
    }
