"""Structured-source full-text acquisition (Phase 2a).

A focused fetch layer, separate from literature_client.search(): given one
already-chosen paper, fetch clean full text from a structured source. No PDF
parsing and no generic-HTML scraping — those are deferred to Phase 2b.
"""
from __future__ import annotations

import re
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
