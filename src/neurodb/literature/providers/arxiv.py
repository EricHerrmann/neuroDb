from __future__ import annotations

import xml.etree.ElementTree as ET

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivProvider(BaseLiteratureProvider):
    name = "arxiv"

    @property
    def endpoint(self) -> str:
        return _URL

    def build_params(self, query: str, limit: int) -> dict:
        return {"search_query": f"all:{query}", "start": 0, "max_results": limit}

    def parse_response(self, response) -> list[dict]:
        root = ET.fromstring(response.text)
        rows = []
        for entry in root.findall("atom:entry", _NS):
            rows.append({
                "title": _text(entry.find("atom:title", _NS)) or "Untitled arXiv result",
                "abstract": _text(entry.find("atom:summary", _NS)) or "",
                "published": _text(entry.find("atom:published", _NS)) or "",
                "doi": _text(entry.find("arxiv:doi", _NS)),
                "id": _text(entry.find("atom:id", _NS)) or "",
            })
        return rows

    def normalize(self, raw: dict) -> dict:
        published = raw.get("published", "")
        year = int(published[:4]) if published[:4].isdigit() else None
        url = raw.get("id", "").replace("http://arxiv.org", "https://arxiv.org") or None
        return {
            "title": raw["title"],
            "doi": raw.get("doi"),
            "url": url,
            "abstract": self._truncate(raw.get("abstract", "")),
            "source_type": "preprint",
            "year": year,
            "citation_count": None,
            "source": self.name,
            "sources": [self.name],
        }


def _text(node) -> str | None:
    if node is None or node.text is None:
        return None
    return " ".join(node.text.split())
