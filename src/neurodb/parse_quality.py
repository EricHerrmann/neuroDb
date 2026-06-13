"""Heuristic parse-quality scoring + gate decision (Phase 2b). Pure, no I/O."""
from __future__ import annotations

import re

from neurodb.fulltext_types import ParsedArtifact

HIGH_DEFAULT = 0.8
LOW_DEFAULT = 0.4
_WORD = re.compile(r"[A-Za-z]{2,}")


def score(artifact: ParsedArtifact) -> float:
    """0..1 confidence that the parse is faithful prose, using ML-free signals."""
    text = "\n".join(s.text for s in artifact.sections).strip()
    if len(text) < 200:
        return 0.0
    printable = sum(1 for c in text if c.isprintable() or c in "\n\t")
    printable_ratio = printable / len(text)
    replacement_ratio = text.count("�") / len(text)
    words = _WORD.findall(text)
    word_chars = sum(len(w) for w in words)
    word_ratio = word_chars / max(1, len(text))
    raw = (0.5 * printable_ratio) + (0.5 * word_ratio) - (5.0 * replacement_ratio)
    return max(0.0, min(1.0, raw))


def gate(confidence: float, *, high: float = HIGH_DEFAULT, low: float = LOW_DEFAULT) -> str:
    if confidence >= high:
        return "accept"
    if confidence < low:
        return "reject"
    return "review"
