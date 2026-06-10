from pathlib import Path

from neurodb.full_text_client import ArxivSourceBackend, SuppliedInput

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "full_text" / "arxiv_sample.html"


class _Paper:
    def __init__(self, url=None, doi=None):
        self.url = url
        self.doi = doi


class _StubHttp:
    def __init__(self, body):
        self._body = body
        self.requested = []

    def get(self, url, **kw):
        self.requested.append(url)
        body = self._body
        class _R:
            status_code = 200
            text = body
            def raise_for_status(self_inner):
                return None
        return _R()


def test_extracts_arxiv_id_from_abs_url():
    backend = ArxivSourceBackend()
    assert backend._arxiv_id(_Paper(url="https://arxiv.org/abs/2401.01234")) == "2401.01234"
    assert backend._arxiv_id(_Paper(url="https://arxiv.org/abs/2401.01234v2")) == "2401.01234v2"
    assert backend._arxiv_id(_Paper(url="https://example.com/x")) is None


def test_can_handle_requires_arxiv_id():
    backend = ArxivSourceBackend()
    assert backend.can_handle(_Paper(url="https://arxiv.org/abs/2401.01234"), None)
    assert not backend.can_handle(_Paper(url="https://pubmed.gov/1"), None)


def test_fetch_parses_sections_from_html():
    backend = ArxivSourceBackend()
    http = _StubHttp(_FIXTURE.read_text())
    result = backend.fetch(_Paper(url="https://arxiv.org/abs/2401.01234"), http, None)
    assert result.text_source == "arxiv_html"
    labels = [s.label for s in result.sections]
    assert any("Introduction" in (l or "") for l in labels)
    assert any("Methods" in (l or "") for l in labels)
    assert "CREB" in result.full_text
    assert "arxiv.org/html/2401.01234" in http.requested[0]
