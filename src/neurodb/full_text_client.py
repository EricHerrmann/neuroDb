"""Structured-source full-text acquisition (Phase 2a).

A focused fetch layer, separate from literature_client.search(): given one
already-chosen paper, fetch clean full text from a structured source. No PDF
parsing and no generic-HTML scraping — those are deferred to Phase 2b.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
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
