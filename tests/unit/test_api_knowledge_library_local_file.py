from neurodb.api.routes.knowledge_library import _phase2b_parse
from neurodb.full_text_client import SuppliedInput


def _paper():
    return type("P", (), {"url": None, "doi": None, "id": 1, "open_access_pdf": None})()


def test_phase2b_parse_reads_local_pdf():
    art = _phase2b_parse(_paper(), SuppliedInput(path="tests/fixtures/sample.pdf"))
    assert art is not None
    assert art.text_source == "pdf_pymupdf"
    assert art.fetched_url == "sample.pdf"
    assert art.sections[0].page == 1
