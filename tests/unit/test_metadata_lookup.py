"""Tests for MetadataLookupClient (Semantic Scholar + Crossref, no network)."""
from __future__ import annotations

import httpx

from neurodb.metadata_lookup import MetadataLookupClient, PaperMetadata

_S2_DOI = {
    "title": "Neural networks and physical systems",
    "year": 1982,
    "abstract": "Computational properties emerge...",
    "url": "https://www.semanticscholar.org/paper/98b4",
    "externalIds": {"DOI": "10.1073/PNAS.79.8.2554"},
    "authors": [{"authorId": "3219867", "name": "J. Hopfield"}],
}

_CROSSREF = {
    "message": {
        "title": ["Neural networks and physical systems"],
        "author": [{"given": "J J", "family": "Hopfield"}],
        "published": {"date-parts": [[1982, 4]]},
        "abstract": "<jats:p>Computational properties emerge...</jats:p>",
        "DOI": "10.1073/pnas.79.8.2554",
    }
}

_S2_SEARCH = {"data": [_S2_DOI]}


class _StubHTTP:
    """Maps URL substrings to (status_code, json_payload)."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url, params=None, headers=None):
        self.calls.append(url)
        for fragment, (status, payload) in self.routes.items():
            if fragment in url:
                return httpx.Response(status, json=payload,
                                      request=httpx.Request("GET", url))
        return httpx.Response(404, json={},
                              request=httpx.Request("GET", url))


def test_doi_lookup_prefers_semantic_scholar():
    http = _StubHTTP({"semanticscholar.org/graph/v1/paper/DOI:": (200, _S2_DOI)})
    found = MetadataLookupClient(http_client=http).lookup(doi="10.1073/pnas.79.8.2554")
    assert isinstance(found, PaperMetadata)
    assert found.source == "semantic_scholar"
    assert found.authors == ["J. Hopfield"]
    assert found.year == 1982
    assert found.doi == "10.1073/PNAS.79.8.2554"
    assert found.abstract.startswith("Computational")


def test_doi_lookup_falls_back_to_crossref():
    http = _StubHTTP({
        "semanticscholar.org/graph/v1/paper/DOI:": (500, {}),
        "api.crossref.org/works/": (200, _CROSSREF),
    })
    found = MetadataLookupClient(http_client=http).lookup(doi="10.1073/pnas.79.8.2554")
    assert found.source == "crossref"
    assert found.authors == ["J J Hopfield"]
    assert found.year == 1982
    assert "<jats:p>" not in found.abstract
    assert found.url == "https://doi.org/10.1073/pnas.79.8.2554"


def test_title_lookup_requires_normalized_title_match():
    http = _StubHTTP({"paper/search": (200, _S2_SEARCH)})
    client = MetadataLookupClient(http_client=http)
    hit = client.lookup(title="Neural networks and physical systems")
    assert hit is not None and hit.authors == ["J. Hopfield"]
    miss = client.lookup(title="A completely different paper title")
    assert miss is None


def test_lookup_returns_none_on_total_failure():
    http = _StubHTTP({})
    assert MetadataLookupClient(http_client=http).lookup(doi="10.1/x") is None
    assert MetadataLookupClient(http_client=http).lookup() is None
