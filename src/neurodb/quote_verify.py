"""Fail-closed quote verification + end-of-turn ledger backstop (Phase 2a, invariant #4)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

_WS = re.compile(r" +")
_NEWLINES = re.compile(r"[\n\r]+")
# Hyphens/dashes U+2010-U+2015 and minus U+2212 -> "-"
_DASHES = re.compile(
    "[" + chr(0x2010) + "-" + chr(0x2015) + chr(0x2212) + "]"
)
# Matches text enclosed in straight (U+0022) or curly (U+201C/U+201D) double quotes.
_Q = chr(0x0022) + chr(0x201C) + chr(0x201D)
_QUOTE_SPAN = re.compile("[" + _Q + "]([^" + _Q + "]+)[" + _Q + "]")


def normalize_quote(text: str) -> str:
    text = _DASHES.sub("-", text)
    text = _NEWLINES.sub("", text)  # strip newlines without inserting a space
    return _WS.sub(" ", text).strip()


def verify_quote(text: str, chunks: list[dict]) -> dict | None:
    """Return a match descriptor if the (normalized) text is a substring of some chunk."""
    needle = normalize_quote(text)
    if not needle:
        return None
    for c in chunks:
        if needle in normalize_quote(c["text"]):
            return {
                "matched": True,
                "chunk_id": c.get("chunk_id"),
                "section": c.get("section"),
                "char_start": c.get("char_start"),
                "char_end": c.get("char_end"),
            }
    return None


@dataclass
class LedgerEntry:
    quoted_text: str
    matched: bool


def _result_text(content) -> str:
    """Extract the JSON text from a tool_result content (string or list-of-blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text") or block.get("content") or "")
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def build_quote_ledger(messages: list[dict]) -> list[LedgerEntry]:
    """Extract verify_quote calls + their matched results from the turn's messages."""
    pending: dict[str, str] = {}  # tool_use_id -> quoted text
    results: dict[str, bool] = {}
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "verify_quote":
                pending[block.get("id")] = (block.get("input") or {}).get("text", "")
            elif block.get("type") == "tool_result":
                tid = block.get("tool_use_id")
                if tid in pending:
                    text = _result_text(block.get("content"))
                    try:
                        results[tid] = bool(json.loads(text).get("matched"))
                    except Exception:
                        results[tid] = False
    return [LedgerEntry(pending[tid], results.get(tid, False)) for tid in pending]


def reconcile_quotes(answer_text: str, ledger: list[LedgerEntry],
                     *, min_quote_chars: int = 25) -> list[str]:
    """Return a warning per quoted span not backed by a matched verify_quote entry."""
    verified = [normalize_quote(e.quoted_text) for e in ledger if e.matched]
    warnings: list[str] = []
    for span in _QUOTE_SPAN.findall(answer_text):
        if len(span) < min_quote_chars:
            continue
        norm = normalize_quote(span)
        if any(v and (v in norm or norm in v) for v in verified):
            continue
        warnings.append(
            f'⚠ The quoted text "{span.strip()}" was not verified against a stored source.'
        )
    return warnings
