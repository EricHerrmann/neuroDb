"""Structured-source full-text acquisition (Phase 2a).

A focused fetch layer, separate from literature_client.search(): given one
already-chosen paper, fetch clean full text from a structured source. No PDF
parsing and no generic-HTML scraping — those are deferred to Phase 2b.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol

from neurodb.chunking import Section


@dataclass
class FullTextResult:
    text_source: str  # arxiv_html | arxiv_src | jats | user_supplied
    sections: list[Section]
    full_text: str


@dataclass
class SuppliedInput:
    url: str | None = None
    text: str | None = None
    format: str | None = None  # txt | md | jats
    path: str | None = None  # local library file path (local-file source)


@dataclass
class AcquireFailure:
    status: str  # unavailable | failed
    reason: str  # needs_parser_phase2b | not_oa | fetch_error | no_source
    message: str


class FullTextBackend(Protocol):
    name: str

    def can_handle(self, paper, supplied: SuppliedInput | None) -> bool: ...

    def fetch(self, paper, http, supplied: SuppliedInput | None) -> FullTextResult | None: ...


def sections_from_labeled_blocks(blocks: list[tuple[str | None, str]]) -> tuple[list[Section], str]:
    """Build offset-correct Sections from (label, text) pairs and the joined full text."""
    sections: list[Section] = []
    parts: list[str] = []
    cursor = 0
    for label, body in blocks:
        body = body.strip()
        if not body:
            continue
        if parts:
            parts.append("\n\n")
            cursor += 2
        start = cursor
        parts.append(body)
        cursor += len(body)
        sections.append(Section(label=label, text=body, char_start=start, char_end=cursor))
    return sections, "".join(parts)


class UserSuppliedBackend:
    name = "user_supplied"

    def can_handle(self, paper, supplied: SuppliedInput | None) -> bool:
        return bool(supplied and supplied.text and supplied.text.strip())

    def fetch(self, paper, http, supplied: SuppliedInput | None) -> FullTextResult | None:
        text = supplied.text
        fmt = (supplied.format or "txt").lower()
        if fmt == "md":
            blocks = _split_markdown(text)
        else:
            blocks = [(None, text)]
        sections, full_text = sections_from_labeled_blocks(blocks)
        if not sections:
            return None
        return FullTextResult("user_supplied", sections, full_text)


_ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)")


class _SectionHTMLParser(HTMLParser):
    """Collect (heading, text) blocks from arXiv-style HTML."""

    def __init__(self):
        super().__init__()
        self.blocks: list[tuple[str | None, str]] = []
        self._label: str | None = None
        self._buf: list[str] = []
        self._in_heading = False
        self._heading: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3"):
            if self._buf:
                self.blocks.append((self._label, " ".join(self._buf).strip()))
                self._buf = []
            self._in_heading = True
            self._heading = []

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3") and self._in_heading:
            self._in_heading = False
            self._label = " ".join(self._heading).strip() or None

    def handle_data(self, data):
        if self._in_heading:
            self._heading.append(data)
        elif data.strip():
            self._buf.append(data.strip())

    def close(self):
        super().close()
        if self._buf:
            self.blocks.append((self._label, " ".join(self._buf).strip()))


class ArxivSourceBackend:
    name = "arxiv"

    def _arxiv_id(self, paper) -> str | None:
        for value in (getattr(paper, "url", None), getattr(paper, "doi", None)):
            if not value:
                continue
            m = _ARXIV_ID_RE.search(value)
            if m:
                return m.group(1)
        return None

    def can_handle(self, paper, supplied: SuppliedInput | None) -> bool:
        return self._arxiv_id(paper) is not None

    def fetch(self, paper, http, supplied: SuppliedInput | None) -> FullTextResult | None:
        arxiv_id = self._arxiv_id(paper)
        if not arxiv_id:
            return None
        resp = http.get(f"https://arxiv.org/html/{arxiv_id}")
        resp.raise_for_status()
        parser = _SectionHTMLParser()
        parser.feed(resp.text)
        parser.close()
        if not parser.blocks:
            return None
        sections, full_text = sections_from_labeled_blocks(parser.blocks)
        if not sections:
            return None
        return FullTextResult("arxiv_html", sections, full_text)


def parse_jats(xml_text: str) -> tuple[list[Section], str]:
    """Extract <sec><title>+text from JATS XML into offset-correct Sections."""
    root = ET.fromstring(xml_text)
    blocks: list[tuple[str | None, str]] = []
    for sec in root.iter("sec"):
        title_el = sec.find("title")
        label = (title_el.text or "").strip() if title_el is not None else None
        texts = [t.strip() for t in sec.itertext() if t.strip()]
        # drop the title text (first item) from the body if present
        body = " ".join(texts[1:] if label and texts and texts[0] == label else texts)
        blocks.append((label, body))
    return sections_from_labeled_blocks(blocks)


class PmcJatsBackend:
    name = "pmc"

    def _pmcid(self, paper, http) -> str | None:
        # Resolve a PMCID via the NCBI ID converter from a PMID or DOI in url/doi.
        ident = None
        for value in (getattr(paper, "doi", None), getattr(paper, "url", None)):
            if value and ("PMC" in value or "/pmc/" in value):
                m = re.search(r"PMC[0-9]+", value)
                if m:
                    return m.group(0)
            if value:
                ident = ident or value
        if not ident:
            return None
        resp = http.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            params={"ids": ident, "format": "json", "tool": "neurodb"},
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        if records and records[0].get("pmcid"):
            return records[0]["pmcid"]
        return None

    def can_handle(self, paper, supplied: SuppliedInput | None) -> bool:
        for value in (getattr(paper, "doi", None), getattr(paper, "url", None)):
            if value:
                return True
        return False

    def _result_from_jats(self, xml_text: str) -> FullTextResult | None:
        sections, full_text = parse_jats(xml_text)
        if not sections:
            return None
        return FullTextResult("jats", sections, full_text)

    def fetch(self, paper, http, supplied: SuppliedInput | None) -> FullTextResult | None:
        pmcid = self._pmcid(paper, http)
        if not pmcid:
            return None
        resp = http.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pmc", "id": pmcid.replace("PMC", ""), "rettype": "full",
                    "retmode": "xml", "tool": "neurodb"},
        )
        resp.raise_for_status()
        return self._result_from_jats(resp.text)


FULL_TEXT_BACKENDS: list[FullTextBackend] = [
    UserSuppliedBackend(),
    ArxivSourceBackend(),
    PmcJatsBackend(),
]


def classify_for_phase2b(paper, supplied: "SuppliedInput | None" = None) -> str:
    """Route a paper to the structured 2a path or the 2b fallback.

    "structured" when 2a can plausibly handle it (user-supplied text, an arXiv id, or a
    PMC-resolvable id); "phase2b" otherwise (publisher landing page, or a user-supplied URL).
    """
    if supplied and supplied.text and supplied.text.strip():
        return "structured"
    if supplied and (supplied.url or supplied.path):
        return "phase2b"
    if ArxivSourceBackend()._arxiv_id(paper) is not None:
        return "structured"
    url = getattr(paper, "url", "") or ""
    doi = getattr(paper, "doi", "") or ""
    if "PMC" in url or "PMC" in doi or "/pmc/" in url:
        return "structured"
    return "phase2b"


def acquire(paper, http, supplied: SuppliedInput | None = None):
    """Return a FullTextResult on success, else an AcquireFailure (never raises for routing)."""
    # 1) explicit user-supplied text
    if supplied and supplied.text and supplied.text.strip():
        return UserSuppliedBackend().fetch(paper, http, supplied) or AcquireFailure(
            "failed", "fetch_error", "Supplied text could not be parsed."
        )

    # 2) structured backends keyed off identifiers
    # arXiv: only attempt when an arXiv ID is extractable
    _arxiv = ArxivSourceBackend()
    if _arxiv._arxiv_id(paper) is not None:
        try:
            result = _arxiv.fetch(paper, http, supplied)
        except Exception as exc:
            return AcquireFailure("failed", "fetch_error", f"{type(exc).__name__}: {exc}")
        if result:
            return result

    # PMC: pre-resolve the PMCID first; skip entirely if none resolves
    if http is not None:
        _pmc = PmcJatsBackend()
        try:
            pmcid = _pmc._pmcid(paper, http)
        except Exception:
            pmcid = None
        if pmcid is not None:
            try:
                result = _pmc.fetch(paper, http, supplied)
            except Exception as exc:
                return AcquireFailure("failed", "fetch_error", f"{type(exc).__name__}: {exc}")
            if result:
                return result
            # PMCID resolved but JATS body was empty — not open-access
            return AcquireFailure(
                "unavailable", "not_oa",
                "No open-access full text available for this source.",
            )

    # 3) raw URL content-type sniff
    candidate = (supplied.url if supplied else None) or getattr(paper, "url", None)
    if candidate and http is not None:
        try:
            resp = http.get(candidate)
            resp.raise_for_status()
        except Exception as exc:
            return AcquireFailure("failed", "fetch_error", f"{type(exc).__name__}: {exc}")
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "text/plain" in ctype or "text/markdown" in ctype:
            fmt = "md" if "markdown" in ctype else "txt"
            return UserSuppliedBackend().fetch(
                paper, http, SuppliedInput(text=resp.text, format=fmt)
            ) or AcquireFailure("failed", "fetch_error", "Empty document.")
        if "xml" in ctype:
            return PmcJatsBackend()._result_from_jats(resp.text) or AcquireFailure(
                "failed", "fetch_error", "Empty JATS document."
            )
        if "html" in ctype or "pdf" in ctype:
            return AcquireFailure(
                "unavailable", "needs_parser_phase2b",
                "This looks like a publisher HTML/PDF page — full-text capture for "
                "those arrives in Phase 2b. Paste the text or supply a .txt/.md/JATS file.",
            )

    return AcquireFailure("unavailable", "no_source", "No structured full-text source found.")


def _split_markdown(md: str) -> list[tuple[str | None, str]]:
    blocks: list[tuple[str | None, str]] = []
    label: str | None = None
    buf: list[str] = []
    for line in md.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if m:
            if buf:
                blocks.append((label, "\n".join(buf).strip()))
                buf = []
            label = m.group(1).strip()
        else:
            buf.append(line)
    if buf:
        blocks.append((label, "\n".join(buf).strip()))
    return blocks
