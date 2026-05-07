"""Research epoch — dataset discovery tools for research workflows.

Migration target: src/neurodb/research/discovery.py
"""
import json
from datetime import datetime, timezone

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from neurodb.schema import ImportQueue, SourceSuggestion

_SUPPORTED_CONNECTORS = ("openneuro",)


def run_search_external(source: str, query: str, limit: int = 10) -> str:
    """Search external connector APIs by keyword. Returns JSON list of candidates."""
    if source == "all":
        results = []
        for name in _SUPPORTED_CONNECTORS:
            results.extend(_search_one(name, query, limit))
        return json.dumps(results)
    if source in _SUPPORTED_CONNECTORS:
        return json.dumps(_search_one(source, query, limit))
    return json.dumps({"error": f"Unknown source '{source}'. Supported: {list(_SUPPORTED_CONNECTORS)}"})


def _search_one(source: str, query: str, limit: int) -> list[dict]:
    if source == "openneuro":
        from neurodb.connectors.openneuro import OpenNeuroConnector
        try:
            raw_list = OpenNeuroConnector().search_by_keyword(query, limit=limit)
            return [{"source": "openneuro", **r} for r in raw_list]
        except Exception as exc:
            return [{"source": "openneuro", "error": str(exc)}]
    return []


def run_suggest_import(
    source: str,
    source_id: str,
    title: str,
    reason: str,
    chapter_ref: str | None,
    metadata: dict,
    engine: Engine,
) -> str:
    """Write a dataset candidate to import_queue. Returns JSON with success flag."""
    now = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        session.add(ImportQueue(
            source=source,
            source_id=source_id,
            title=title,
            reason=reason,
            chapter_ref=chapter_ref,
            status="pending",
            metadata_json=json.dumps(metadata) if metadata else None,
            suggested_at=now,
        ))
        session.commit()
    return json.dumps({"success": True, "source": source, "source_id": source_id})


def run_suggest_learning_source(
    suggestion_type: str,
    reference: str,
    display_name: str,
    reason: str,
    engine: Engine,
) -> str:
    """Queue a paper, study, or dataset as a candidate learning source."""
    now = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        session.add(SourceSuggestion(
            suggestion_type=suggestion_type,
            reference=reference,
            display_name=display_name,
            reason=reason,
            status="pending",
            suggested_at=now,
        ))
        session.commit()
    return json.dumps({"success": True, "reference": reference})


def run_suggest_new_source(
    reference: str,
    display_name: str,
    reason: str,
    engine: Engine,
) -> str:
    """Log an entirely new database or API as a candidate connector."""
    now = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        session.add(SourceSuggestion(
            suggestion_type="new_connector",
            reference=reference,
            display_name=display_name,
            reason=reason,
            status="pending",
            suggested_at=now,
        ))
        session.commit()
    return json.dumps({"success": True, "reference": reference})


DISCOVERY_TOOLS = [
    {
        "name": "search_external",
        "description": (
            "Search external neuroscience databases by keyword. "
            "Use source='openneuro' for OpenNeuro, or source='all' to search all supported sources. "
            "Returns candidate datasets that can then be queued for import via suggest_import."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Connector name ('openneuro') or 'all' to search all supported sources.",
                },
                "query": {
                    "type": "string",
                    "description": "Keyword or phrase to search for.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results per source (default 10).",
                },
            },
            "required": ["source", "query"],
        },
    },
    {
        "name": "suggest_import",
        "description": (
            "Queue a dataset for the user to review and optionally import. "
            "Call this after search_external identifies a relevant dataset. "
            "Nothing is imported automatically — the user confirms in the Suggestions tab."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Connector name (e.g. 'openneuro')."},
                "source_id": {"type": "string", "description": "Dataset ID within the source."},
                "title": {"type": "string", "description": "Dataset title from the external API."},
                "reason": {"type": "string", "description": "Why this dataset is relevant to the user's question."},
                "chapter_ref": {"type": "string", "description": "Current chapter context, if set (optional)."},
            },
            "required": ["source", "source_id", "title", "reason"],
        },
    },
    {
        "name": "suggest_learning_source",
        "description": (
            "Queue a paper, study, or dataset as a candidate learning source for the registry. "
            "The user reviews and promotes it in the Suggestions tab."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "suggestion_type": {
                    "type": "string",
                    "description": "Type of learning source: 'learning_source'.",
                },
                "reference": {
                    "type": "string",
                    "description": "DOI, URL, or source_id identifying the source.",
                },
                "display_name": {"type": "string", "description": "Human-readable name."},
                "reason": {"type": "string", "description": "Why this source is relevant."},
            },
            "required": ["suggestion_type", "reference", "display_name", "reason"],
        },
    },
    {
        "name": "suggest_new_source",
        "description": (
            "Log an entirely new database or API as a candidate connector. "
            "Adding it to the system requires a separate engineering step — "
            "this only records the suggestion for the user to review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "URL or name of the new source."},
                "display_name": {"type": "string", "description": "Human-readable name."},
                "reason": {"type": "string", "description": "Why this source would be valuable."},
            },
            "required": ["reference", "display_name", "reason"],
        },
    },
]
