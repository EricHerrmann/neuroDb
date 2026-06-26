import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from neurodb import db as dbpkg
from neurodb.literature.client import LiteratureSearchClient
from neurodb.literature import registry
from neurodb.literature.providers.base import BaseLiteratureProvider
from neurodb.schema import LiteratureSearch


class _StubProvider(BaseLiteratureProvider):
    def __init__(self, name, rows, error=None):
        super().__init__(http=None)
        self.name = name
        self._rows = rows
        self._error = error

    @property
    def endpoint(self):
        return "x"

    def build_params(self, query, limit):
        return {}

    def parse_response(self, response):
        return []

    def normalize(self, raw):
        return raw

    def search(self, query, limit):
        if self._error:
            return [], self._error
        return self._rows, None


def _engine():
    eng = create_engine("duckdb:///:memory:")
    dbpkg.init_db(eng)
    return eng


def _rec(doi, source, cites=None):
    return {"title": "T", "doi": doi, "url": None, "abstract": "a",
            "source_type": "paper", "year": 2020, "citation_count": cites,
            "source": source, "sources": [source]}


def test_envelope_merges_and_reports_providers(monkeypatch):
    eng = _engine()
    providers = [
        _StubProvider("pubmed", [_rec("10.1/x", "pubmed", 2)]),
        _StubProvider("openalex", [_rec("10.1/x", "openalex", 9), _rec("10.1/y", "openalex", 1)]),
        _StubProvider("crossref", [], error="HTTPError: 429"),
    ]
    monkeypatch.setattr(registry, "build_active_providers", lambda http, timeout=10.0: providers)
    client = LiteratureSearchClient(eng, http_client=object())
    env = client.search("ltp", limit=10)
    assert env["result_count"] == 2  # 10.1/x merged
    assert env["providers"]["pubmed"]["status"] == "ok"
    assert env["providers"]["crossref"]["status"] == "error"
    assert env["providers"]["crossref"]["error"] == "HTTPError: 429"
    merged = next(r for r in env["results"] if r["doi"] == "10.1/x")
    assert merged["citation_count"] == 9
    assert set(merged["sources"]) == {"pubmed", "openalex"}


def test_logs_provider_counts_json(monkeypatch):
    eng = _engine()
    providers = [_StubProvider("pubmed", [_rec("10.1/x", "pubmed", 2)])]
    monkeypatch.setattr(registry, "build_active_providers", lambda http, timeout=10.0: providers)
    client = LiteratureSearchClient(eng, http_client=object())
    client.search("ltp")
    with Session(eng) as s:
        row = s.execute(select(LiteratureSearch)).scalars().one()
    counts = json.loads(row.provider_counts_json)
    assert counts["pubmed"] == 1
    assert row.pubmed_count == 1
