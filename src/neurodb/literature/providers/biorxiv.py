"""bioRxiv/medRxiv provider.

bioRxiv has no general keyword-search API, so this queries Europe PMC
restricted to preprint sources (SRC:PPR) and tags results as the biorxiv
provider. Confirm SRC filter syntax against current Europe PMC docs.
"""
from __future__ import annotations

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class BiorxivProvider(BaseLiteratureProvider):
    name = "biorxiv"

    @property
    def endpoint(self) -> str:
        return _URL

    def build_params(self, query: str, limit: int) -> dict:
        return {"query": f"({query}) AND SRC:PPR", "format": "json", "pageSize": limit,
                "resultType": "core"}

    def parse_response(self, response) -> list[dict]:
        return (response.json().get("resultList", {}) or {}).get("result", []) or []

    def normalize(self, raw: dict) -> dict:
        year_text = raw.get("pubYear")
        return {
            "title": raw.get("title") or "Untitled preprint",
            "doi": raw.get("doi"),
            "url": self._doi_url(raw.get("doi")),
            "abstract": self._truncate(raw.get("abstractText") or ""),
            "source_type": "preprint",
            "year": int(year_text) if year_text and str(year_text).isdigit() else None,
            "citation_count": raw.get("citedByCount"),
            "source": self.name,
            "sources": [self.name],
        }
