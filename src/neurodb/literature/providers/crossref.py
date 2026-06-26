from __future__ import annotations

import re

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://api.crossref.org/works"
_TAG = re.compile(r"<[^>]+>")


class CrossrefProvider(BaseLiteratureProvider):
    name = "crossref"
    uses_polite_pool = True

    @property
    def endpoint(self) -> str:
        return _URL

    def build_params(self, query: str, limit: int) -> dict:
        return {"query": query, "rows": limit}

    def parse_response(self, response) -> list[dict]:
        return (response.json().get("message", {}) or {}).get("items", []) or []

    def normalize(self, raw: dict) -> dict:
        titles = raw.get("title") or []
        title = titles[0] if titles else "Untitled Crossref result"
        parts = (raw.get("published", {}) or {}).get("date-parts") or [[None]]
        year = parts[0][0] if parts and parts[0] else None
        abstract = _TAG.sub(" ", raw.get("abstract") or "")
        return {
            "title": title,
            "doi": raw.get("DOI"),
            "url": self._doi_url(raw.get("DOI")),
            "abstract": self._truncate(abstract),
            "source_type": self._classify_source_type([raw.get("type") or ""], "paper"),
            "year": int(year) if isinstance(year, int) else None,
            "citation_count": raw.get("is-referenced-by-count"),
            "source": self.name,
            "sources": [self.name],
        }
