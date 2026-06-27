from __future__ import annotations

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://api.openalex.org/works"


class OpenAlexProvider(BaseLiteratureProvider):
    name = "openalex"
    uses_polite_pool = True

    @property
    def endpoint(self) -> str:
        return _URL

    def build_params(self, query: str, limit: int) -> dict:
        return {"search": query, "per-page": limit}

    def parse_response(self, response) -> list[dict]:
        return response.json().get("results", []) or []

    def normalize(self, raw: dict) -> dict:
        doi = (raw.get("doi") or "").replace("https://doi.org/", "") or None
        return {
            "title": raw.get("display_name") or raw.get("title") or "Untitled OpenAlex result",
            "doi": doi,
            "url": raw.get("id") or self._doi_url(doi),
            "abstract": self._truncate(_invert_abstract(raw.get("abstract_inverted_index"))),
            "source_type": self._classify_source_type([raw.get("type") or ""], "paper"),
            "year": raw.get("publication_year"),
            "citation_count": raw.get("cited_by_count"),
            "source": self.name,
            "sources": [self.name],
        }


def _invert_abstract(index: dict | None) -> str:
    if not index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in index.items():
        for i in idxs:
            positions.append((i, word))
    return " ".join(word for _i, word in sorted(positions))
