"""Shared full-text parse artifact (Phase 2b). Decouples parsers from the client."""
from __future__ import annotations

from dataclasses import dataclass

from neurodb.chunking import Section


@dataclass
class ParsedArtifact:
    sections: list[Section]
    parse_confidence: float
    text_source: str  # pdf_docling | pdf_pymupdf | html_extracted
    fetched_url: str | None = None
