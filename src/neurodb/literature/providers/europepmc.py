from __future__ import annotations

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class EuropePmcProvider(BaseLiteratureProvider):
    name = "europepmc"

    @property
    def endpoint(self) -> str:
        return _URL

    def build_params(self, query: str, limit: int) -> dict:
        return {"query": query, "format": "json", "pageSize": limit, "resultType": "core"}

    def parse_response(self, response) -> list[dict]:
        return (response.json().get("resultList", {}) or {}).get("result", []) or []

    def normalize(self, raw: dict) -> dict:
        year_text = raw.get("pubYear")
        return {
            "title": raw.get("title") or "Untitled Europe PMC result",
            "doi": raw.get("doi"),
            "url": self._doi_url(raw.get("doi")),
            "abstract": self._truncate(raw.get("abstractText") or ""),
            "source_type": self._classify_source_type([raw.get("pubType") or ""], "paper"),
            "year": int(year_text) if year_text and str(year_text).isdigit() else None,
            "citation_count": raw.get("citedByCount"),
            "source": self.name,
            "sources": [self.name],
        }
