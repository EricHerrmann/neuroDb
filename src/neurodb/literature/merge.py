"""Dedup, enrich-merge, and rank literature results across providers."""
from __future__ import annotations

import re

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_SPECIFICITY = {"review": 3, "paper": 2, "preprint": 1}


def _norm_title(title: str) -> str:
    lowered = (title or "").lower()
    return " ".join(_PUNCT.sub(" ", lowered).split())


def _key(record: dict) -> str:
    doi = (record.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    return f"ty:{_norm_title(record.get('title', ''))}|{record.get('year')}"


def _merge_pair(base: dict, other: dict) -> dict:
    merged = dict(base)
    # longest abstract wins
    if len(other.get("abstract") or "") > len(merged.get("abstract") or ""):
        merged["abstract"] = other.get("abstract")
    # max citation count
    counts = [c for c in (base.get("citation_count"), other.get("citation_count")) if c is not None]
    merged["citation_count"] = max(counts) if counts else None
    # most specific source_type
    if _SPECIFICITY.get(other.get("source_type"), 0) > _SPECIFICITY.get(merged.get("source_type"), 0):
        merged["source_type"] = other.get("source_type")
    # prefer a real (non-DOI-only) url
    if not merged.get("url") or (merged["url"] or "").startswith("https://doi.org/"):
        if other.get("url"):
            merged["url"] = other["url"]
    # union of sources, sorted/stable
    merged["sources"] = sorted(set(base.get("sources") or []) | set(other.get("sources") or []))
    # keep doi if either has one
    merged["doi"] = base.get("doi") or other.get("doi")
    return merged


def _rank_key(record: dict):
    cites = record.get("citation_count")
    year = record.get("year")
    return (
        0 if cites is not None else 1, -(cites or 0),
        0 if year is not None else 1, -(year or 0),
        record.get("title") or "",
    )


def dedup_and_merge(results: list[dict], limit: int) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for record in results:
        key = _key(record)
        if key in merged:
            merged[key] = _merge_pair(merged[key], record)
        else:
            merged[key] = dict(record)
            order.append(key)
    deduped = [merged[k] for k in order]
    deduped.sort(key=_rank_key)
    return deduped[:limit]
