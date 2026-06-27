"""Client-level tests for the literature search fan-out.

Adapted from the pre-registry sequential implementation: the client now fans
out concurrently across registry providers, so this uses a thread-safe
URL-routing fake (not an ordered pop list) and asserts the merge/envelope
contract rather than provider call order.
"""
import json

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.literature_client import LiteratureSearchClient
from neurodb.literature.providers.arxiv import ArxivProvider
from neurodb.schema import Base, LiteratureSearch


@pytest.fixture(autouse=True)
def _clear_literature_env(monkeypatch):
    """These tests exercise the real registry; isolate them from an ambient
    LITERATURE_PROVIDERS_DISABLED in the developer's .env (e.g. semantic_scholar)."""
    monkeypatch.delenv("LITERATURE_PROVIDERS_DISABLED", raising=False)


PUBMED_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>123</PMID>
      <Article>
        <ArticleTitle>Hippocampal long-term potentiation and memory</ArticleTitle>
        <Abstract><AbstractText>Long-term potentiation is a model of synaptic plasticity.</AbstractText></Abstract>
        <Journal><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal>
        <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
        <ELocationID EIdType="doi">10.1000/ltp</ELocationID>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <published>2024-01-15T10:00:00Z</published>
    <title>Predictive coding and synaptic plasticity</title>
    <summary>A preprint on plasticity mechanisms.</summary>
    <arxiv:doi>10.1000/arxivpublished</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.05678v2</id>
    <published>2024-02-20T10:00:00Z</published>
    <title>Cortical maps without a DOI</title>
    <summary>An unpublished preprint.</summary>
  </entry>
</feed>
"""

EMPTY_FEED = "<feed xmlns='http://www.w3.org/2005/Atom'></feed>"


class _Response:
    def __init__(self, json_data=None, text=""):
        self._json_data = json_data if json_data is not None else {}
        self.text = text
        self.headers = {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        return None


class _RouteHttp:
    """Routes GETs to a response by URL substring; thread-safe (CPython list.append).

    Unmatched URLs return an empty JSON response, so providers without an
    explicit route (e.g. the JSON-based OpenAlex/Crossref/Europe PMC/bioRxiv)
    yield an empty-but-successful result.
    """

    def __init__(self, routes, default=None):
        self.routes = routes
        self.default = default if default is not None else _Response(json_data={}, text="")
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, {"params": params, "headers": headers, "timeout": timeout}))
        for needle, resp in self.routes.items():
            if needle in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return self.default


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_literature_search_schema_table_created():
    engine = _engine()
    assert "literature_searches" in Base.metadata.tables
    with Session(engine) as session:
        session.add(
            LiteratureSearch(
                query="plasticity",
                pubmed_count=1,
                semantic_scholar_count=0,
                results_json="[]",
                searched_at="2026-05-05T00:00:00",
            )
        )
        session.commit()
        assert session.query(LiteratureSearch).count() == 1


def test_search_parses_pubmed_and_semantic_scholar_and_dedups_by_doi():
    engine = _engine()
    fake = _RouteHttp({
        "esearch": _Response({"esearchresult": {"idlist": ["123"]}}),
        "efetch": _Response(text=PUBMED_XML),
        "semanticscholar": _Response({
            "data": [
                {
                    "title": "Duplicate Semantic Scholar LTP",
                    "abstract": "Same DOI should be deduplicated.",
                    "year": 2023,
                    "citationCount": 42,
                    "externalIds": {"DOI": "10.1000/ltp"},
                    "publicationTypes": ["JournalArticle"],
                },
                {
                    "title": "A review of cortical plasticity",
                    "abstract": "Review abstract.",
                    "year": 2022,
                    "citationCount": 12,
                    "externalIds": {"DOI": "10.1000/review"},
                    "publicationTypes": ["Review"],
                },
            ]
        }),
        "arxiv": _Response(text=EMPTY_FEED),
    })

    out = LiteratureSearchClient(engine, http_client=fake).search("LTP")
    results = out["results"]

    assert out["result_count"] == 2
    # Ranked by citation count desc: merged LTP (42) then review (12).
    assert [row["doi"] for row in results] == ["10.1000/ltp", "10.1000/review"]
    # The LTP record was contributed by both pubmed and semantic_scholar (merged).
    assert set(results[0]["sources"]) == {"pubmed", "semantic_scholar"}
    assert results[0]["citation_count"] == 42
    assert results[1]["source_type"] == "review"
    # Semantic Scholar review with no source URL falls back to the DOI resolver.
    assert results[1]["url"] == "https://doi.org/10.1000/review"
    # Semantic Scholar request must ask for the url field.
    s2_call = next(c for c in fake.calls if "semanticscholar" in c[0])
    assert "url" in s2_call[1]["params"]["fields"].split(",")

    # Provider statuses report success with per-source counts.
    assert out["providers"]["pubmed"] == {"status": "ok", "count": 1, "error": None}
    assert out["providers"]["semantic_scholar"] == {"status": "ok", "count": 2, "error": None}

    with Session(engine) as session:
        row = session.query(LiteratureSearch).one()
        assert row.query == "LTP"
        assert row.pubmed_count == 1
        assert row.semantic_scholar_count == 2
        assert len(json.loads(row.results_json)) == 2
        assert json.loads(row.provider_counts_json)["semantic_scholar"] == 2


def test_semantic_scholar_prefers_source_url_over_doi():
    engine = _engine()
    fake = _RouteHttp({
        "esearch": _Response({"esearchresult": {"idlist": []}}),
        "semanticscholar": _Response({
            "data": [{
                "title": "Paper with a real landing page",
                "abstract": "Has both a url and a DOI.",
                "year": 2025,
                "citationCount": 7,
                "url": "https://www.semanticscholar.org/paper/abc123",
                "externalIds": {"DOI": "10.1000/haspage"},
                "publicationTypes": ["JournalArticle"],
            }]
        }),
        "arxiv": _Response(text=EMPTY_FEED),
    })

    out = LiteratureSearchClient(engine, http_client=fake).search("plasticity")

    hit = next(r for r in out["results"] if r["doi"] == "10.1000/haspage")
    assert hit["url"] == "https://www.semanticscholar.org/paper/abc123"


def test_provider_failure_is_reported_as_error_not_silent_empty():
    """A failing provider must surface status=error, distinct from an empty success."""
    engine = _engine()
    fake = _RouteHttp({
        "esearch": httpx.TimeoutException("pubmed down"),
        "semanticscholar": _Response({
            "data": [{
                "title": "Semantic Scholar fallback",
                "abstract": "Fallback result.",
                "year": 2024,
                "citationCount": 3,
                "externalIds": {"DOI": "10.1000/fallback"},
                "publicationTypes": ["JournalArticle"],
            }]
        }),
        "arxiv": _Response(text=EMPTY_FEED),
    })

    out = LiteratureSearchClient(engine, http_client=fake).search("plasticity")

    assert any(r["doi"] == "10.1000/fallback" for r in out["results"])
    # PubMed failed -> error status with a message; arXiv succeeded with zero hits.
    assert out["providers"]["pubmed"]["status"] == "error"
    assert out["providers"]["pubmed"]["error"]
    assert out["providers"]["pubmed"]["count"] == 0
    assert out["providers"]["semantic_scholar"]["status"] == "ok"
    assert out["providers"]["arxiv"] == {"status": "ok", "count": 0, "error": None}
    with Session(engine) as session:
        row = session.query(LiteratureSearch).one()
        assert row.pubmed_count == 0
        assert row.semantic_scholar_count == 1


def test_all_providers_empty_yields_zero_results_all_ok():
    """No matches anywhere is a successful empty search, not an error."""
    engine = _engine()
    fake = _RouteHttp({
        "esearch": _Response({"esearchresult": {"idlist": []}}),
        "semanticscholar": _Response({"data": []}),
        "arxiv": _Response(text=EMPTY_FEED),
    })

    out = LiteratureSearchClient(engine, http_client=fake).search("no such topic")

    assert out["result_count"] == 0
    assert out["results"] == []
    assert all(p["status"] == "ok" for p in out["providers"].values())


def test_search_merges_arxiv_and_logs_arxiv_count():
    engine = _engine()
    fake = _RouteHttp({
        "esearch": _Response({"esearchresult": {"idlist": ["123"]}}),
        "efetch": _Response(text=PUBMED_XML),
        "semanticscholar": _Response({"data": []}),
        "arxiv": _Response(text=ARXIV_XML),
    })

    out = LiteratureSearchClient(engine, http_client=fake).search("plasticity")

    arxiv_rows = [row for row in out["results"] if "arxiv" in row["sources"]]
    assert len(arxiv_rows) >= 1
    assert out["providers"]["arxiv"] == {"status": "ok", "count": 2, "error": None}

    with Session(engine) as session:
        row = session.query(LiteratureSearch).one()
        assert row.arxiv_count == 2


def test_search_degrades_gracefully_when_arxiv_fails():
    engine = _engine()
    fake = _RouteHttp({
        "esearch": _Response({"esearchresult": {"idlist": []}}),
        "semanticscholar": _Response({"data": []}),
        "arxiv": httpx.TimeoutException("arxiv down"),
    })

    out = LiteratureSearchClient(engine, http_client=fake).search("plasticity")

    assert out["result_count"] == 0
    assert out["providers"]["arxiv"]["status"] == "error"
    with Session(engine) as session:
        assert session.query(LiteratureSearch).one().arxiv_count == 0


def test_arxiv_endpoint_uses_https_and_client_follows_redirects():
    """arXiv's http endpoint 301-redirects; the client must use https and follow redirects."""
    assert ArxivProvider(http=None).endpoint.startswith("https://")
    client = LiteratureSearchClient(_engine())
    assert client._http.follow_redirects is True


def test_default_timeout_is_ten_seconds():
    """Generous default timeout so slow PubMed efetch does not silently return empty."""
    client = LiteratureSearchClient(_engine())
    assert client._timeout == 10.0
