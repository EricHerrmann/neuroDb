from neurodb.pdf_parser import parse_pdf


def test_pymupdf_fallback_produces_sections_with_pages():
    with open("tests/fixtures/sample.pdf", "rb") as f:
        data = f.read()
    art = parse_pdf(data, docling_convert=lambda b: (_ for _ in ()).throw(RuntimeError("no ml")))
    assert art.text_source == "pdf_pymupdf"
    assert art.sections and art.sections[0].page == 1
    assert "memory" in "\n".join(s.text for s in art.sections).lower()


def test_both_parsers_fail_raises():
    import pytest
    with pytest.raises(Exception):
        parse_pdf(b"%PDF-broken",
                  docling_convert=lambda b: (_ for _ in ()).throw(RuntimeError("x")))


def test_default_no_docling_uses_pymupdf():
    with open("tests/fixtures/sample.pdf", "rb") as f:
        data = f.read()
    art = parse_pdf(data)  # docling_convert defaults to None
    assert art.text_source == "pdf_pymupdf"
    assert art.parse_confidence >= 0.0
