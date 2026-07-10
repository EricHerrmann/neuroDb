"""Backfill NULL bibliographic Paper fields on full-text acquisition (workstream 2).

Pure decision logic (select_backfill_fields) is separated from the write, which is
injected as `set_fields` because DuckDB requires the route's FK-safe updater for
`papers` rows. Never overwrites a non-null curated field; never raises out of
backfill_paper_metadata — failures become warnings so acquisition is never blocked.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from neurodb.db import get_session
from neurodb.metadata_lookup import PaperMetadata
from neurodb.schema import Paper


@dataclass
class BackfillResult:
    filled: dict[str, str] = field(default_factory=dict)   # field -> source label
    values: dict[str, object] = field(default_factory=dict)  # field -> written value
    warnings: list[str] = field(default_factory=list)


def select_backfill_fields(current: dict, found: PaperMetadata) -> dict[str, object]:
    """Return only the target fields that are currently NULL/empty. Pure."""
    fields: dict[str, object] = {}
    if not current.get("authors_json") and found.authors:
        fields["authors_json"] = json.dumps(found.authors)
    if not current.get("abstract") and found.abstract:
        fields["abstract"] = found.abstract
    if current.get("year") is None and found.year is not None:
        fields["year"] = found.year
    if not current.get("doi") and found.doi:
        fields["doi"] = found.doi
    if not current.get("url") and found.url:
        fields["url"] = found.url
    return fields


def backfill_paper_metadata(engine, source_id: int, *,
                            metadata_client, set_fields) -> BackfillResult:
    """Fill NULL bibliographic fields for one paper. Warnings, never exceptions."""
    with get_session(engine) as session:
        paper = session.get(Paper, source_id)
        if paper is None:
            return BackfillResult(warnings=[f"paper {source_id} not found"])
        current = {
            "authors_json": paper.authors_json,
            "abstract": paper.abstract,
            "year": paper.year,
            "doi": paper.doi,
            "url": paper.url,
        }
        title = paper.title

    try:
        found = metadata_client.lookup(
            doi=current["doi"],
            title=None if current["doi"] else title,
        )
    except Exception as exc:
        return BackfillResult(warnings=[f"metadata lookup failed: {exc}"])
    if found is None:
        return BackfillResult(warnings=[
            "no external metadata found (DOI and title lookup empty); "
            "bibliographic fields left NULL",
        ])

    fields = select_backfill_fields(current, found)
    if not fields:
        return BackfillResult()
    try:
        set_fields(**fields)
    except Exception as exc:
        return BackfillResult(warnings=[f"metadata backfill write failed: {exc}"])
    return BackfillResult(
        filled={name: found.source for name in fields},
        values=fields,
    )
