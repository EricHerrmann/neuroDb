from neurodb.literature.providers.base import BaseLiteratureProvider


class _Resp:
    def __init__(self, json_data=None, text="", headers=None):
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


class _Http:
    def __init__(self, resp=None, raise_exc=None):
        self.resp = resp
        self.raise_exc = raise_exc
        self.last_params = None

    def get(self, url, params=None, headers=None, timeout=None):
        self.last_params = params
        if self.raise_exc:
            raise self.raise_exc
        return self.resp


class _Fake(BaseLiteratureProvider):
    name = "fake"
    uses_polite_pool = True

    @property
    def endpoint(self):
        return "https://example.test/search"

    def build_params(self, query, limit):
        return {"q": query, "n": limit}

    def parse_response(self, response):
        return response.json()["rows"]

    def normalize(self, raw):
        return {
            "title": raw["title"],
            "doi": raw.get("doi"),
            "url": self._doi_url(raw.get("doi")),
            "abstract": self._truncate(raw.get("abstract", "")),
            "source_type": self._classify_source_type(raw.get("types", []), "paper"),
            "year": raw.get("year"),
            "citation_count": raw.get("cites"),
            "source": self.name,
            "sources": [self.name],
        }


def test_search_returns_normalized_rows():
    http = _Http(resp=_Resp(json_data={"rows": [{"title": "T", "doi": "10.1/x", "year": 2020}]}))
    provider = _Fake(http, contact_email="me@example.com")
    results, error = provider.search("ltp", 5)
    assert error is None
    assert results[0]["title"] == "T"
    assert results[0]["source"] == "fake"
    assert results[0]["url"] == "https://doi.org/10.1/x"


def test_search_captures_exception_as_error():
    http = _Http(raise_exc=RuntimeError("boom"))
    provider = _Fake(http)
    results, error = provider.search("ltp", 5)
    assert results == []
    assert "boom" in error


def test_polite_pool_adds_mailto_when_email_present():
    http = _Http(resp=_Resp(json_data={"rows": []}))
    provider = _Fake(http, contact_email="me@example.com")
    provider.search("ltp", 5)
    assert http.last_params.get("mailto") == "me@example.com"


def test_polite_pool_absent_without_email():
    http = _Http(resp=_Resp(json_data={"rows": []}))
    provider = _Fake(http, contact_email=None)
    provider.search("ltp", 5)
    assert "mailto" not in http.last_params


def test_classify_source_type_prefers_review():
    assert _Fake.__mro__  # provider class importable
    p = _Fake(_Http(resp=_Resp(json_data={"rows": []})))
    assert p._classify_source_type(["Journal Article", "Review"], "paper") == "review"
    assert p._classify_source_type(["Journal Article"], "paper") == "paper"


def test_truncate_collapses_and_limits():
    assert _Fake._truncate("  a   b  ") == "a b"
    assert _Fake._truncate("x" * 400).endswith("...")
    assert _Fake._truncate("") is None
