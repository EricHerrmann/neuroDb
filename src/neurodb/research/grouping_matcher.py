"""Research epoch — LLM-based grouping suggestion with new-grouping proposals.

Replaces substring matching (LOG-062). Modeled on hypothesis_review.py: one
forced tool call, telemetry via record_model_call, fail-closed via the
run_suggest_groupings wrapper.
"""
from __future__ import annotations

import json
import time

from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.db.grouping_store import (
    get_grouping,
    get_or_create_grouping,
    link_grouping,
    list_groupings,
)
from neurodb.db.grouping_types import GROUPING_TYPES
from neurodb.model_telemetry import record_model_call, record_system_warning


_SYSTEM_PROMPT = """You categorize neuroscience research text.
You are given a piece of text and a list of existing groupings of one kind.
Identify which existing groupings are genuinely relevant to the text, and propose
any clearly warranted new groupings of the same kind that are not already in the list.
Be conservative: only include groupings the text is actually about.
Call submit_groupings exactly once with your structured answer."""

_SUBMIT_GROUPINGS_TOOL = {
    "name": "submit_groupings",
    "description": (
        "Record which existing groupings are relevant to the text and propose any "
        "new ones. Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "relevant_existing": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "reason"],
                },
            },
            "proposed_new": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "parent_name": {"type": ["string", "null"]},
                    },
                    "required": ["name", "parent_name"],
                },
            },
        },
        "required": ["relevant_existing", "proposed_new"],
    },
}


def _build_prompt(anchor_text: str, gtype: str, candidates: list[dict]) -> str:
    return json.dumps({
        "instruction": (
            f"Classify the text against existing '{gtype}' groupings. Return relevant "
            "existing ones by id, and propose clearly warranted new ones. "
            "Call submit_groupings once."
        ),
        "grouping_kind": gtype,
        "text": anchor_text,
        "existing_groupings": [
            {"id": c["id"], "name": c["name"], "parent_id": c.get("parent_id")}
            for c in candidates
        ],
    }, indent=2)


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _parse_response(response) -> dict:
    from neurodb.config.model_client import ModelResponse
    if isinstance(response, ModelResponse):
        for block in response.content:
            if block.type == "tool_use" and block.tool_name == "submit_groupings":
                inputs = block.tool_input or {}
                return {
                    "relevant_existing": _as_list(inputs.get("relevant_existing")),
                    "proposed_new": _as_list(inputs.get("proposed_new")),
                }
    return {"relevant_existing": [], "proposed_new": []}


def suggest_groupings(
    engine: Engine,
    *,
    anchor_type: str,
    anchor_id: int,
    anchor_text: str,
    gtype: str,
    model_client,
    model: str,
    model_provider: str,
    max_tokens: int,
) -> dict:
    """Match anchor_text against existing groupings of gtype and propose new ones.

    Persists pending grouping_links for matches (with parent rollup) and proposed
    groupings for new items. Returns a summary dict.
    """
    with get_session(engine) as session:
        candidates = list_groupings(session, gtype=gtype, status="active")

    started = time.monotonic()
    response = model_client.create_message(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        tools=[model_client.format_tool(_SUBMIT_GROUPINGS_TOOL)],
        messages=[{"role": "user", "content": _build_prompt(anchor_text, gtype, candidates)}],
        tool_choice="required",
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    record_model_call(
        engine,
        task_type="agent.extract.groupings",
        provider=model_provider,
        model=model,
        mode="neuro_research",
        response=response,
        iteration=1,
        elapsed_ms=elapsed_ms,
    )

    parsed = _parse_response(response)
    allow_proposal = GROUPING_TYPES[gtype].allow_agent_proposal
    suggested: list[str] = []
    proposed: list[str] = []

    with get_session(engine) as session:
        for item in parsed["relevant_existing"]:
            gid = item.get("id") if isinstance(item, dict) else None
            if not isinstance(gid, int):
                continue
            g = get_grouping(session, gid)
            if g is None or g.type != gtype or g.status != "active":
                continue
            link_grouping(session, g.id, anchor_type, anchor_id, status="pending")
            suggested.append(g.name)
            if g.parent_id is not None:
                link_grouping(session, g.parent_id, anchor_type, anchor_id, status="pending")
                parent = get_grouping(session, g.parent_id)
                if parent is not None:
                    suggested.append(parent.name)

        if allow_proposal:
            for item in parsed["proposed_new"]:
                name = str((item or {}).get("name") or "").strip()
                if not name:
                    continue
                g = get_or_create_grouping(session, gtype, name, status="proposed")
                link_grouping(session, g.id, anchor_type, anchor_id, status="pending")
                if g.status == "proposed":
                    proposed.append(g.name)
                else:
                    suggested.append(g.name)

    return {
        "anchor_type": anchor_type,
        "anchor_id": anchor_id,
        "gtype": gtype,
        "suggested": list(dict.fromkeys(suggested)),
        "proposed": list(dict.fromkeys(proposed)),
    }


def run_suggest_groupings(
    engine: Engine,
    *,
    anchor_type: str,
    anchor_id: int,
    anchor_text: str,
    gtypes: tuple[str, ...] = ("topic", "concept"),
) -> None:
    """Fail-closed wrapper: resolve a route per type and run the matcher.

    On any failure for a type, write a SystemWarning and persist nothing for that
    type. The anchor (e.g. the question) is unaffected.
    """
    from neurodb.config.provider_factory import build_provider_clients
    from neurodb.config.task_router import TaskRouter

    for gtype in gtypes:
        try:
            route = TaskRouter(build_provider_clients()).route(
                "agent.extract.groupings", engine=engine
            )
            suggest_groupings(
                engine,
                anchor_type=anchor_type,
                anchor_id=anchor_id,
                anchor_text=anchor_text,
                gtype=gtype,
                model_client=route.model_client,
                model=route.model_id,
                model_provider=route.provider,
                max_tokens=route.max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 — fail closed for any matcher error
            record_system_warning(
                engine,
                warning_type="grouping_match_failed",
                severity="warning",
                task_type="agent.extract.groupings",
                message=f"{gtype}: {str(exc)[:300]}",
            )
