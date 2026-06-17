from neurodb.full_text_client import classify_for_phase2b, SuppliedInput


def _paper(url=None, doi=None):
    return type("P", (), {"url": url, "doi": doi, "id": 1})()


def test_publisher_html_routes_to_phase2b():
    assert classify_for_phase2b(_paper(url="https://www.semanticscholar.org/paper/abc")) == "phase2b"


def test_user_supplied_pdf_url_routes_to_phase2b():
    assert classify_for_phase2b(_paper(), SuppliedInput(url="http://x/p.pdf")) == "phase2b"


def test_user_supplied_text_stays_structured():
    assert classify_for_phase2b(_paper(), SuppliedInput(text="pasted body")) == "structured"


def test_arxiv_stays_structured():
    assert classify_for_phase2b(_paper(url="https://arxiv.org/abs/1234.5678")) == "structured"


def test_pmc_stays_structured():
    assert classify_for_phase2b(_paper(url="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123/")) == "structured"


def test_supplied_path_routes_to_phase2b():
    from neurodb.full_text_client import classify_for_phase2b, SuppliedInput
    paper = type("P", (), {"url": None, "doi": None, "id": 1})()
    assert classify_for_phase2b(paper, SuppliedInput(path="/lib/x.pdf")) == "phase2b"
