"""Section-aware chunking for full-text RAG (Phase 2a). Pure, no I/O."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Section:
    label: str | None
    text: str
    char_start: int
    char_end: int


@dataclass
class Chunk:
    chunk_index: int
    text: str
    section: str | None
    char_start: int
    char_end: int


def chunk_sections(
    sections: list[Section], *, max_chars: int = 1200, overlap: int = 150
) -> list[Chunk]:
    """Chunk each section on its own boundaries; split oversize ones with overlap.

    Offsets are absolute (indexing into the normalized full text). Sections that
    are blank after stripping contribute no chunks.
    """
    chunks: list[Chunk] = []
    index = 0
    step = max(1, max_chars - overlap)
    for sec in sections:
        if not sec.text.strip():
            continue
        if len(sec.text) <= max_chars:
            chunks.append(
                Chunk(index, sec.text, sec.label, sec.char_start, sec.char_end)
            )
            index += 1
            continue
        pos = 0
        while pos < len(sec.text):
            piece = sec.text[pos : pos + max_chars]
            if not piece.strip():
                break
            start = sec.char_start + pos
            chunks.append(Chunk(index, piece, sec.label, start, start + len(piece)))
            index += 1
            pos += step
    return chunks
