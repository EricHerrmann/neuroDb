from neurodb.full_text_client import AcquireFailure, FullTextResult, SuppliedInput, acquire


class _Paper:
    def __init__(self, url=None, doi=None):
        self.url = url
        self.doi = doi


class _Resp:
    def __init__(self, body="", headers=None, status=200):
        self.text = body
        self.headers = headers or {}
        self.status_code = status

    def raise_for_status(self):
        return None


class _Http:
    def __init__(self, resp):
        self._resp = resp

    def get(self, url, **kw):
        return self._resp


def test_user_supplied_text_wins():
    result = acquire(_Paper(), http=None, supplied=SuppliedInput(text="hello", format="txt"))
    assert isinstance(result, FullTextResult)
    assert result.text_source == "user_supplied"


def test_generic_html_url_is_rejected_to_phase2b():
    http = _Http(_Resp(body="<html>...</html>", headers={"Content-Type": "text/html"}))
    result = acquire(_Paper(url="https://journal.example/article/1"), http=http, supplied=None)
    assert isinstance(result, AcquireFailure)
    assert result.reason == "needs_parser_phase2b"


def test_pdf_url_is_rejected_to_phase2b():
    http = _Http(_Resp(headers={"Content-Type": "application/pdf"}))
    result = acquire(_Paper(url="https://x/y.pdf"), http=http, supplied=None)
    assert isinstance(result, AcquireFailure)
    assert result.reason == "needs_parser_phase2b"


def test_no_source_returns_unavailable():
    result = acquire(_Paper(), http=None, supplied=None)
    assert isinstance(result, AcquireFailure)
    assert result.reason == "no_source"
