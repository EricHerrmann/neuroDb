import pytest
from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.parse_quality import gate, score


def _artifact(text, source="pdf_pymupdf"):
    return ParsedArtifact(
        sections=[Section(label=None, text=text, char_start=0, char_end=len(text))],
        parse_confidence=0.0, text_source=source,
    )


def test_clean_prose_scores_high():
    prose = ("The hippocampus supports memory consolidation. " * 40)
    assert score(_artifact(prose)) >= 0.8


def test_empty_or_garbage_scores_low():
    assert score(_artifact("")) < 0.4
    assert score(_artifact("\x00\x01� � \x02 " * 20)) < 0.4


@pytest.mark.parametrize("conf,expected", [(0.95, "accept"), (0.6, "review"), (0.2, "reject")])
def test_gate_thresholds(conf, expected):
    assert gate(conf, high=0.8, low=0.4) == expected
