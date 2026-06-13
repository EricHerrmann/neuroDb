"""Discover an open-access PDF URL for a paper (Phase 2b). All HTTP is injected."""
from __future__ import annotations

import re

_DOI = re.compile(r"10\.\d+/[^\s\"'<>]+", re.I)
_PDF_META = re.compile(
    r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']', re.I)
_PDF_ANCHOR = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)


def _doi(paper, http, *, email: str | None) -> str | None:
    if getattr(paper, "doi", None):
        m = _DOI.search(paper.doi)
        if m:
            return m.group(0)
    url = getattr(paper, "url", None)
    if url and "pubmed" in url:
        m = re.search(r"/(\d+)", url)
        if m:
            try:
                resp = http.get(
                    "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
                    params={"ids": m.group(1), "format": "json", "tool": "neurodb"})
                resp.raise_for_status()
                rec = (resp.json().get("records") or [{}])[0]
                return rec.get("doi")
            except Exception:
                return None
    return None


def _unpaywall(doi: str, http, *, email: str) -> str | None:
    try:
        resp = http.get(f"https://api.unpaywall.org/v2/{doi}", params={"email": email})
        resp.raise_for_status()
        loc = (resp.json() or {}).get("best_oa_location") or {}
        return loc.get("url_for_pdf")
    except Exception:
        return None


def _landing_scan(url: str, http) -> str | None:
    try:
        resp = http.get(url)
        resp.raise_for_status()
    except Exception:
        return None
    if "html" not in (resp.headers.get("Content-Type") or "").lower():
        return None
    m = _PDF_META.search(resp.text) or _PDF_ANCHOR.search(resp.text)
    return m.group(1) if m else None


def find_pdf_url(paper, http, *, unpaywall_email: str | None, s2_pdf_url: str | None) -> str | None:
    """Return the first OA PDF URL found, else None. Order: Unpaywall, S2, landing scan."""
    doi = _doi(paper, http, email=unpaywall_email)
    if doi and unpaywall_email:
        pdf = _unpaywall(doi, http, email=unpaywall_email)
        if pdf:
            return pdf
    if s2_pdf_url:
        return s2_pdf_url
    url = getattr(paper, "url", None)
    if url:
        return _landing_scan(url, http)
    return None
