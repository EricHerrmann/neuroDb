"""External bibliographic metadata lookup for acquisition backfill.

Source precedence (spec workstream 2): Semantic Scholar by DOI, Crossref by DOI,
then Semantic Scholar title search gated on a normalized-title match. Every
network failure degrades to None; callers record a warning and never block.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_S2_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
_S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_S2_FIELDS = "title,abstract,year,authors,externalIds,url"
_CROSSREF_URL = "https://api.crossref.org/works/{doi}"
_TAG = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@dataclass
class PaperMetadata:
    source: str  # "semantic_scholar" | "crossref"
    authors: list[str] = field(default_factory=list)
    abstract: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None


def _norm_title(title: str) -> str:
    return _NON_ALNUM.sub(" ", (title or "").lower()).strip()


class MetadataLookupClient:
    """Provider-agnostic bibliographic lookup used by backfill."""

    def __init__(self, http_client=None, timeout: float = 10.0) -> None:
        self._http = http_client or httpx.Client(timeout=timeout, follow_redirects=True)

    def lookup(self, *, doi: str | None = None,
               title: str | None = None) -> PaperMetadata | None:
        if doi:
            found = self._s2_by_doi(doi) or self._crossref_by_doi(doi)
            if found is not None:
                return found
        if title:
            return self._s2_by_title(title)
        return None

    def _s2_headers(self) -> dict:
        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        return {"x-api-key": api_key} if api_key else {}

    def _s2_by_doi(self, doi: str) -> PaperMetadata | None:
        try:
            resp = self._http.get(
                _S2_PAPER_URL.format(doi=doi),
                params={"fields": _S2_FIELDS},
                headers=self._s2_headers(),
            )
            if resp.status_code != 200:
                return None
            return self._normalize_s2(resp.json())
        except Exception:
            logger.exception("Semantic Scholar DOI lookup failed for %s", doi)
            return None

    def _s2_by_title(self, title: str) -> PaperMetadata | None:
        try:
            resp = self._http.get(
                _S2_SEARCH_URL,
                params={"query": title, "limit": 1, "fields": _S2_FIELDS},
                headers=self._s2_headers(),
            )
            if resp.status_code != 200:
                return None
            data = resp.json().get("data") or []
            if not data:
                return None
            hit = data[0]
            if _norm_title(hit.get("title") or "") != _norm_title(title):
                return None  # wrong paper; do not contaminate curated metadata
            return self._normalize_s2(hit)
        except Exception:
            logger.exception("Semantic Scholar title lookup failed for %r", title)
            return None

    def _crossref_by_doi(self, doi: str) -> PaperMetadata | None:
        try:
            resp = self._http.get(_CROSSREF_URL.format(doi=doi))
            if resp.status_code != 200:
                return None
            return self._normalize_crossref(resp.json().get("message") or {})
        except Exception:
            logger.exception("Crossref DOI lookup failed for %s", doi)
            return None

    @staticmethod
    def _normalize_s2(raw: dict) -> PaperMetadata | None:
        if not raw:
            return None
        doi = (raw.get("externalIds") or {}).get("DOI")
        return PaperMetadata(
            source="semantic_scholar",
            authors=[a["name"] for a in (raw.get("authors") or []) if a.get("name")],
            abstract=(raw.get("abstract") or "").strip() or None,
            year=raw.get("year"),
            doi=doi,
            url=(raw.get("url") or "").strip() or None,
        )

    @staticmethod
    def _normalize_crossref(message: dict) -> PaperMetadata | None:
        if not message:
            return None
        authors = [
            " ".join(part for part in [a.get("given"), a.get("family")] if part)
            for a in (message.get("author") or [])
        ]
        parts = (message.get("published") or {}).get("date-parts") or [[None]]
        year = parts[0][0] if parts and parts[0] else None
        abstract = _TAG.sub(" ", message.get("abstract") or "").strip()
        doi = message.get("DOI")
        return PaperMetadata(
            source="crossref",
            authors=[a for a in authors if a],
            abstract=" ".join(abstract.split()) or None,
            year=int(year) if isinstance(year, int) else None,
            doi=doi,
            url=f"https://doi.org/{doi}" if doi else None,
        )
