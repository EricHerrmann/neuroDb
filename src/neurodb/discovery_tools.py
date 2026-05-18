"""Research epoch — dataset discovery tools for research workflows.

Migration target: src/neurodb/research/discovery.py
"""
import json
from datetime import UTC, datetime

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from neurodb.connectors import ALL_CONNECTORS
from neurodb.schema import ImportQueue, SourceSuggestion

_CONNECTORS = {connector.SOURCE_NAME: connector for connector in ALL_CONNECTORS}


def _supported_connectors() -> list[str]:
    return sorted(_CONNECTORS)


def run_search_external(source: str, query: str, limit: int = 10) -> str:
    """Search external connector APIs by keyword. Returns JSON list of candidates."""
    if source == "all":
        results = []
        for name in _supported_connectors():
            results.extend(_search_one(name, query, limit))
        return json.dumps(results)
    if source in _CONNECTORS:
        return json.dumps(_search_one(source, query, limit))
    return json.dumps({"error": f"Unknown source '{source}'. Supported: {_supported_connectors()}"})


def run_inspect_external_dataset(source: str, reference: str) -> str:
    """Fetch one external dataset by source-native id or supported URL."""
    resolved = _resolve_external_reference(source, reference)
    if "error" in resolved:
        return json.dumps(resolved)

    connector_cls = _CONNECTORS[resolved["source"]]
    try:
        raw = connector_cls().fetch_by_id(resolved["source_id"])
    except NotImplementedError as exc:
        return json.dumps({"error": str(exc), **resolved})
    except Exception as exc:
        return json.dumps({"error": str(exc), **resolved})
    return json.dumps({**resolved, "raw": raw})


def _resolve_external_reference(source: str, reference: str) -> dict:
    if source != "auto":
        connector_cls = _CONNECTORS.get(source)
        if connector_cls is None:
            return {"error": f"Unknown source '{source}'. Supported: {_supported_connectors()}"}
        source_id = connector_cls.extract_source_id(reference) or reference.strip()
        if not source_id:
            return {"error": "reference is required", "source": source}
        return {"source": source, "source_id": source_id}

    matches = [
        {"source": connector_cls.SOURCE_NAME, "source_id": source_id}
        for connector_cls in _CONNECTORS.values()
        if (source_id := connector_cls.extract_source_id(reference))
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return {
            "error": "Reference matched multiple sources; pass source explicitly.",
            "matches": matches,
        }
    return {
        "error": (
            "Could not infer source from reference. Pass source explicitly as one of: "
            f"{_supported_connectors()}"
        )
    }


def _search_one(source: str, query: str, limit: int) -> list[dict]:
    connector_cls = _CONNECTORS[source]
    try:
        raw_list = connector_cls().search_by_keyword(query, limit=limit)
        return [{"source": source, **r} for r in raw_list]
    except Exception as exc:
        return [{"source": source, "error": str(exc)}]


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
    now = datetime.now(UTC).isoformat()
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
    now = datetime.now(UTC).isoformat()
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
    now = datetime.now(UTC).isoformat()
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
            "Use source='all' to search all supported sources, or one of the registered "
            "connector names. "
            "Returns candidate datasets that can then be queued for import via suggest_import."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Connector name or 'all' to search all supported sources.",
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
        "name": "inspect_external_dataset",
        "description": (
            "Fetch metadata for one external dataset using a dataset URL or source-native id. "
            "Use source='auto' for supported provider URLs, or pass a connector name for bare ids."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Connector name, or 'auto' to infer it from a supported URL.",
                },
                "reference": {
                    "type": "string",
                    "description": "Dataset URL, source-prefixed id, or source-native id.",
                },
            },
            "required": ["source", "reference"],
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
                "reason": {
                    "type": "string",
                    "description": "Why this dataset is relevant to the user's question.",
                },
                "chapter_ref": {
                    "type": "string",
                    "description": "Current chapter context, if set (optional).",
                },
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

READ_ONLY_DISCOVERY_TOOLS = [
    tool
    for tool in DISCOVERY_TOOLS
    if tool["name"] in {"search_external", "inspect_external_dataset"}
]
