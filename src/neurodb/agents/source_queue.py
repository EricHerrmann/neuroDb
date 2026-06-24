"""Shared write path for queuing/nominating Knowledge Library sources.

Both the Tutor (`queue_source`) and Research (`nominate_paper`) agents queue
candidate papers into the same `papers` table. This module owns the one
deduplication / merge / conflict / insert path so the two agents cannot drift
apart, and so abstract-grounding behavior (tier assignment, year capture) is
identical regardless of which agent did the queuing.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from neurodb.schema import Paper
from neurodb.temporal import parse_year


def normalize_title(title: str) -> str:
    """Normalize titles for exact deduplication."""
    value = unicodedata.normalize("NFKD", title.strip().lower())
    value = re.sub(r"[^\w\s]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def merge_existing_paper_metadata(paper: Paper, inputs: dict) -> list[str]:
    """Fill missing review metadata when a queued source is re-submitted."""
    updates: list[str] = []
    for field in ("doi", "url", "abstract"):
        value = (inputs.get(field) or "").strip()
        if value and not getattr(paper, field):
            setattr(paper, field, value)
            updates.append(field)
    year = parse_year(inputs.get("year"))
    if year and not paper.year:
        paper.year = year
        updates.append("year")
    if "abstract" in updates and paper.data_tier == "metadata":
        paper.data_tier = "abstract"
        updates.append("data_tier")
    return updates


def find_paper_metadata_conflicts(paper: Paper, inputs: dict) -> list[dict]:
    """Return submitted metadata values that conflict with an existing paper record."""
    conflicts: list[dict] = []
    for field in ("doi", "url", "abstract"):
        submitted = (inputs.get(field) or "").strip()
        current = getattr(paper, field)
        if submitted and current and submitted != current:
            conflicts.append({"field": field, "current": current, "submitted": submitted})
    year = parse_year(inputs.get("year"))
    if year and paper.year and year != paper.year:
        conflicts.append({"field": "year", "current": paper.year, "submitted": year})
    return conflicts


def replace_existing_paper_metadata(paper: Paper, inputs: dict) -> tuple[list[str], dict, dict]:
    """Replace explicitly corrected review metadata on an existing paper."""
    updated_fields: list[str] = []
    previous_values: dict = {}
    current_values: dict = {}
    for field in ("doi", "url", "abstract"):
        if field not in inputs:
            continue
        value = (inputs.get(field) or "").strip()
        if not value:
            continue
        if value != getattr(paper, field):
            previous_values[field] = getattr(paper, field)
            setattr(paper, field, value)
            current_values[field] = value
            updated_fields.append(field)
    if "year" in inputs:
        value = parse_year(inputs.get("year"))
        if value is None:
            return updated_fields, previous_values, current_values
        if value != paper.year:
            previous_values["year"] = paper.year
            paper.year = value
            current_values["year"] = value
            updated_fields.append("year")
    return updated_fields, previous_values, current_values


def queue_or_update_paper(session: Session, inputs: dict, *, link_topics: bool = False) -> dict:
    """Insert a new pending paper or merge into an existing one.

    Single write path shared by both agents. Deduplicates by DOI then normalized
    title; on a hit it merges missing fields and reports conflicts; on a miss it
    inserts a pending row. The data tier follows from the abstract: a stored
    abstract makes it `abstract` tier, otherwise `metadata` (the flag for AG3).
    Conflicts are returned in the result; callers add any agent-specific
    next-action hint.
    """
    title = inputs["title"].strip()
    normalized = normalize_title(title)
    doi = (inputs.get("doi") or "").strip() or None

    existing = session.query(Paper).filter_by(doi=doi).first() if doi else None
    if existing is None:
        existing = session.query(Paper).filter_by(normalized_title=normalized).first()
    if existing is not None:
        if existing.status == "removed":
            return {
                "status": "removed_exists",
                "id": existing.id,
                "updated_fields": [],
                "message": (
                    "A legacy removed Knowledge Library source matches this DOI/title. "
                    "Delete it from the Removed filter or choose how to handle its "
                    "references before queueing this source again."
                ),
                "next_action": (
                    "Open Knowledge Library with the Removed filter, then use Delete "
                    "or replace references."
                ),
            }
        updated_fields = merge_existing_paper_metadata(existing, inputs)
        conflicts = find_paper_metadata_conflicts(existing, inputs)
        session.flush()
        result = {
            "status": "updated" if updated_fields else "already_exists",
            "id": existing.id,
            "updated_fields": updated_fields,
        }
        if conflicts:
            result["conflicts"] = conflicts
        return result

    abstract = (inputs.get("abstract") or "").strip() or None
    authors = inputs.get("authors") or []
    row = Paper(
        title=title,
        normalized_title=normalized,
        doi=doi,
        url=(inputs.get("url") or None),
        source_type=inputs["source_type"],
        topic_context=inputs["topic_context"],
        status="pending",
        queued_at=datetime.now(UTC).isoformat(),
        abstract=abstract,
        year=parse_year(inputs.get("year")),
        authors_json=json.dumps(authors) if authors else None,
        data_tier="abstract" if abstract else "metadata",
        currency_status="current",
    )
    session.add(row)
    session.flush()
    paper_id = row.id
    if link_topics:
        topics = inputs.get("topics") or []
        if topics:
            from neurodb.db.grouping_store import get_or_create_grouping, link_grouping

            for topic_name in topics:
                grouping = get_or_create_grouping(session, "topic", topic_name)
                link_grouping(session, grouping.id, "paper", paper_id, status="confirmed")
    return {"status": "queued", "id": paper_id}
