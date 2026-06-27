from __future__ import annotations

import os

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


class SemanticScholarProvider(BaseLiteratureProvider):
    name = "semantic_scholar"

    @property
    def endpoint(self) -> str:
        return _URL

    def _headers(self) -> dict:
        api_key = self._api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        return {"x-api-key": api_key} if api_key else {}

    def build_params(self, query: str, limit: int) -> dict:
        return {
            "query": query,
            "limit": limit,
            "fields": "title,abstract,year,citationCount,externalIds,publicationTypes,url",
        }

    def parse_response(self, response) -> list[dict]:
        return response.json().get("data", []) or []

    def normalize(self, raw: dict) -> dict:
        doi = (raw.get("externalIds") or {}).get("DOI")
        return {
            "title": raw.get("title") or "Untitled Semantic Scholar result",
            "doi": doi,
            "url": (raw.get("url") or "").strip() or self._doi_url(doi),
            "abstract": self._truncate(raw.get("abstract") or ""),
            "source_type": self._classify_source_type(raw.get("publicationTypes") or [], "paper"),
            "year": raw.get("year"),
            "citation_count": raw.get("citationCount"),
            "source": self.name,
            "sources": [self.name],
        }
