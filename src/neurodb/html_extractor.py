"""Generic publisher HTML -> ParsedArtifact (Phase 2b). No page anchors."""
from __future__ import annotations

from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.parse_quality import score


def extract_html(html: str, *, extractor=None) -> ParsedArtifact:
    if extractor is None:
        import trafilatura

        def extractor(h):
            return trafilatura.extract(h) or ""
    text = (extractor(html) or "").strip()
    sections = ([Section(label=None, text=text, char_start=0, char_end=len(text))]
                if text else [])
    art = ParsedArtifact(sections, 0.0, "html_extracted")
    art.parse_confidence = score(art) if sections else 0.0
    return art
