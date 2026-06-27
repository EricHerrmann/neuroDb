from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from neurodb.literature.providers.base import BaseLiteratureProvider

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class PubmedProvider(BaseLiteratureProvider):
    name = "pubmed"

    @property
    def endpoint(self) -> str:
        return _EFETCH

    def build_params(self, query: str, limit: int) -> dict:
        return {"db": "pubmed", "term": query, "retmode": "json", "retmax": str(limit)}

    def _fetch(self, query: str, limit: int):
        api_key = self._api_key or os.environ.get("NCBI_API_KEY")
        params = self.build_params(query, limit)
        if api_key:
            params["api_key"] = api_key
        headers = self._request_headers()
        search_resp = self._http.get(_ESEARCH, params=params, headers=headers, timeout=self._timeout)
        search_resp.raise_for_status()
        pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return _EmptyXml()
        fetch_params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
        if api_key:
            fetch_params["api_key"] = api_key
        fetch_resp = self._http.get(_EFETCH, params=fetch_params, headers=headers, timeout=self._timeout)
        fetch_resp.raise_for_status()
        return fetch_resp

    def parse_response(self, response) -> list[dict]:
        text = getattr(response, "text", "") or ""
        if not text.strip():
            return []
        root = ET.fromstring(text)
        rows = []
        for article in root.findall(".//PubmedArticle"):
            title = _text(article.find(".//ArticleTitle")) or "Untitled PubMed result"
            abstract = " ".join(
                p for p in (_text(n) for n in article.findall(".//AbstractText")) if p
            )
            year_text = _text(article.find(".//PubDate/Year"))
            pub_types = [_text(n) for n in article.findall(".//PublicationType") if _text(n)]
            doi = None
            for n in article.findall(".//ELocationID") + article.findall(".//ArticleId"):
                if n.attrib.get("EIdType") == "doi" or n.attrib.get("IdType") == "doi":
                    doi = _text(n)
                    break
            pmid = _text(article.find(".//PMID"))
            rows.append({"title": title, "abstract": abstract, "year": year_text,
                         "pub_types": pub_types, "doi": doi, "pmid": pmid})
        return rows

    def normalize(self, raw: dict) -> dict:
        year_text = raw.get("year")
        pmid = (raw.get("pmid") or "").strip()
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else self._doi_url(raw.get("doi"))
        return {
            "title": raw["title"],
            "doi": raw.get("doi"),
            "url": url,
            "abstract": self._truncate(raw.get("abstract", "")),
            "source_type": self._classify_source_type(raw.get("pub_types", []), "paper"),
            "year": int(year_text) if year_text and str(year_text).isdigit() else None,
            "citation_count": None,
            "source": self.name,
            "sources": [self.name],
        }


class _EmptyXml:
    text = ""

    def raise_for_status(self):
        return None


def _text(node) -> str | None:
    if node is None or node.text is None:
        return None
    return " ".join(node.text.split())
