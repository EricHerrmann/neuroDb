from neurodb.oa_locator import find_pdf_url


class _Resp:
    def __init__(self, *, json_data=None, text="", ctype="application/json"):
        self._json = json_data or {}
        self.text = text
        self.headers = {"Content-Type": ctype}

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class _Http:
    def __init__(self, routes):
        self.routes = routes  # list[(predicate, _Resp)]

    def get(self, url, params=None, **kw):
        for pred, resp in self.routes:
            if pred(url, params):
                return resp
        return _Resp(json_data={})


def _paper(doi=None, url=None):
    return type("P", (), {"doi": doi, "url": url, "id": 1})()


def test_unpaywall_pdf_wins():
    http = _Http([
        (lambda u, p: "unpaywall" in u,
         _Resp(json_data={"best_oa_location": {"url_for_pdf": "http://oa/x.pdf"}})),
    ])
    assert find_pdf_url(_paper(doi="10.1000/xyz123"), http, unpaywall_email="a@b.c",
                        s2_pdf_url=None) == "http://oa/x.pdf"


def test_s2_openaccess_fallback():
    http = _Http([(lambda u, p: "unpaywall" in u, _Resp(json_data={}))])
    assert find_pdf_url(_paper(doi="10.1000/xyz123"), http, unpaywall_email="a@b.c",
                        s2_pdf_url="http://s2/y.pdf") == "http://s2/y.pdf"


def test_landing_page_citation_pdf_url():
    page = '<meta name="citation_pdf_url" content="http://pub/z.pdf">'
    http = _Http([
        (lambda u, p: "unpaywall" in u, _Resp(json_data={})),
        (lambda u, p: u == "http://pub/article", _Resp(text=page, ctype="text/html")),
    ])
    assert find_pdf_url(_paper(url="http://pub/article"), http,
                        unpaywall_email="a@b.c", s2_pdf_url=None) == "http://pub/z.pdf"


def test_none_when_no_oa():
    http = _Http([(lambda u, p: True, _Resp(json_data={}, text="", ctype="text/html"))])
    assert find_pdf_url(_paper(url="http://pub/article"), http,
                        unpaywall_email="a@b.c", s2_pdf_url=None) is None
