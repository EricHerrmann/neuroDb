"""Live literature search client for PubMed and Semantic Scholar."""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.schema import LiteratureSearch

_PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


class LiteratureSearchClient:
    """Search PubMed and Semantic Scholar and return normalized paper results."""

    def __init__(
        self,
        engine: Engine,
        http_client: Any | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._engine = engine
        self._http = http_client or httpx.Client(timeout=timeout)
        self._timeout = timeout

    def search(self, query: str, limit: int = 10) -> list[dict]:
        pubmed_results = self._search_pubmed(query, limit)
        semantic_results = self._search_semantic_scholar(query, limit)
        results = _dedup_by_doi(pubmed_results + semantic_results)
        self._log_search(query, len(pubmed_results), len(semantic_results), results)
        return results

    def _search_pubmed(self, query: str, limit: int) -> list[dict]:
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": str(limit),
        }
        api_key = os.environ.get("NCBI_API_KEY")
        if api_key:
            params["api_key"] = api_key

        try:
            search_response = self._http.get(
                _PUBMED_ESEARCH_URL,
                params=params,
                timeout=self._timeout,
            )
            search_response.raise_for_status()
            pmids = search_response.json().get("esearchresult", {}).get("idlist", [])
            if not pmids:
                return []

            fetch_params = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
            }
            if api_key:
                fetch_params["api_key"] = api_key
            fetch_response = self._http.get(
                _PUBMED_EFETCH_URL,
                params=fetch_params,
                timeout=self._timeout,
            )
            fetch_response.raise_for_status()
            return _parse_pubmed_xml(fetch_response.text)
        except Exception:
            return []

    def _search_semantic_scholar(self, query: str, limit: int) -> list[dict]:
        headers = {}
        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key

        try:
            response = self._http.get(
                _SEMANTIC_SCHOLAR_URL,
                params={
                    "query": query,
                    "limit": limit,
                    "fields": "title,abstract,year,citationCount,externalIds,publicationTypes",
                },
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return [_normalize_semantic_scholar(row) for row in response.json().get("data", [])]
        except Exception:
            return []

    def _log_search(
        self,
        query: str,
        pubmed_count: int,
        semantic_scholar_count: int,
        results: list[dict],
    ) -> None:
        with get_session(self._engine) as session:
            session.add(
                LiteratureSearch(
                    query=query,
                    pubmed_count=pubmed_count,
                    semantic_scholar_count=semantic_scholar_count,
                    results_json=json.dumps(results),
                    searched_at=datetime.now(timezone.utc).isoformat(),
                )
            )


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    results = []
    for article in root.findall(".//PubmedArticle"):
        title = _text(article.find(".//ArticleTitle")) or "Untitled PubMed result"
        abstract_parts = [_text(node) for node in article.findall(".//AbstractText")]
        abstract = " ".join(part for part in abstract_parts if part)
        year_text = _text(article.find(".//PubDate/Year"))
        publication_types = [
            _text(node).lower()
            for node in article.findall(".//PublicationType")
            if _text(node)
        ]
        doi = None
        for node in article.findall(".//ELocationID") + article.findall(".//ArticleId"):
            if (node.attrib.get("EIdType") == "doi" or node.attrib.get("IdType") == "doi"):
                doi = _text(node)
                break
        results.append(
            {
                "title": title,
                "doi": doi,
                "abstract": _truncate(abstract),
                "source_type": "review" if any("review" in p for p in publication_types) else "paper",
                "year": int(year_text) if year_text and year_text.isdigit() else None,
                "citation_count": None,
                "source": "pubmed",
            }
        )
    return results


def _normalize_semantic_scholar(row: dict) -> dict:
    publication_types = [str(value).lower() for value in row.get("publicationTypes") or []]
    return {
        "title": row.get("title") or "Untitled Semantic Scholar result",
        "doi": (row.get("externalIds") or {}).get("DOI"),
        "abstract": _truncate(row.get("abstract") or ""),
        "source_type": "review" if any("review" in value for value in publication_types) else "paper",
        "year": row.get("year"),
        "citation_count": row.get("citationCount"),
        "source": "semantic_scholar",
    }


def _dedup_by_doi(results: list[dict]) -> list[dict]:
    seen_dois = set()
    deduped = []
    for result in results:
        doi = (result.get("doi") or "").strip().lower()
        if doi:
            if doi in seen_dois:
                continue
            seen_dois.add(doi)
        deduped.append(result)
    return deduped


def _truncate(text: str, limit: int = 300) -> str | None:
    value = " ".join((text or "").split())
    if not value:
        return None
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def _text(node) -> str | None:
    if node is None or node.text is None:
        return None
    return " ".join(node.text.split())
