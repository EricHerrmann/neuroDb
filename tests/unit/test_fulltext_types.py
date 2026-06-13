from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact


def test_parsed_artifact_holds_sections_confidence_source():
    a = ParsedArtifact(
        sections=[Section(label=None, text="x", char_start=0, char_end=1, page=1)],
        parse_confidence=0.9,
        text_source="pdf_docling",
        fetched_url="http://x/p.pdf",
    )
    assert a.parse_confidence == 0.9
    assert a.text_source == "pdf_docling"
    assert a.sections[0].page == 1
