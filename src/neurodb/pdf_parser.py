"""PDF -> ParsedArtifact (Phase 2b). PyMuPDF parser with page anchors.

A `docling_convert` seam is accepted for a future high-fidelity Docling adapter (deferred);
it defaults to None, so the PyMuPDF path is used today.
"""
from __future__ import annotations

from collections.abc import Callable

from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.parse_quality import score


def _pymupdf_sections(data: bytes) -> list[Section]:
    import fitz  # pymupdf
    doc = fitz.open(stream=data, filetype="pdf")
    sections: list[Section] = []
    cursor = 0
    for pno in range(doc.page_count):
        text = doc.load_page(pno).get_text("text").strip()
        if not text:
            continue
        start = cursor
        cursor += len(text) + 2
        sections.append(Section(label=f"p{pno + 1}", text=text,
                                char_start=start, char_end=start + len(text), page=pno + 1))
    return sections


def parse_pdf(data: bytes, *, docling_convert: Callable[[bytes], list[Section]] | None = None,
              text_source: str = "pdf_docling") -> ParsedArtifact:
    """Parse a PDF into a ParsedArtifact. Uses the injected docling_convert if provided and it
    yields sections; otherwise (the default today) uses PyMuPDF. Raises if no text is extractable."""
    if docling_convert is not None:
        try:
            sections = docling_convert(data)
            if sections:
                art = ParsedArtifact(sections, 0.0, text_source)
                art.parse_confidence = score(art)
                return art
        except Exception:
            pass
    sections = _pymupdf_sections(data)
    if not sections:
        raise ValueError("PDF produced no extractable text")
    art = ParsedArtifact(sections, 0.0, "pdf_pymupdf")
    art.parse_confidence = score(art)
    return art
