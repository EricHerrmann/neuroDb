"""Shared Learning Plans agent tools (registered on tutor + research agents)."""
from __future__ import annotations

import json

from sqlalchemy.engine import Engine

from neurodb.research.learning_plans import propose_plan, propose_plan_update

_STEP_ITEM = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["read", "action"]},
        "source": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "source_type": {"type": "string"},
                "topic_context": {"type": "string"},
            },
            "required": ["title"],
        },
        "action_text": {"type": "string"},
    },
    "required": ["type"],
}

LEARNING_PLAN_TOOLS = [
    {
        "name": "propose_learning_plan",
        "description": (
            "Propose a multi-step study plan for the user to review. Steps are ordered; "
            "each is a 'read' (a source to read) or an 'action' (a task). The plan is saved "
            "as 'proposed' until the user approves it in the Study Plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "origin_prompt": {"type": "string"},
                "steps": {"type": "array", "items": _STEP_ITEM},
            },
            "required": ["title", "origin_prompt", "steps"],
        },
    },
    {
        "name": "update_learning_plan",
        "description": (
            "Propose changes to an existing plan: add steps and/or mark confirmed steps for "
            "removal. Changes are pending until the user confirms them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "integer"},
                "add_steps": {"type": "array", "items": _STEP_ITEM},
                "remove_step_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["plan_id"],
        },
    },
]


def execute_propose_learning_plan(engine: Engine, inputs: dict, *, origin_agent: str = "tutor",
                                  origin_session_id: int | None = None) -> str:
    agent = inputs.get("origin_agent", origin_agent)
    out = propose_plan(
        engine, title=inputs["title"], origin_prompt=inputs["origin_prompt"],
        origin_agent=agent, steps=inputs["steps"], origin_session_id=origin_session_id,
    )
    return json.dumps(out)


def execute_update_learning_plan(engine: Engine, inputs: dict) -> str:
    out = propose_plan_update(
        engine, plan_id=inputs["plan_id"],
        add_steps=inputs.get("add_steps"), remove_step_ids=inputs.get("remove_step_ids"),
    )
    return json.dumps({"id": out["id"], "pending_change_count": out["pending_change_count"]})


def build_learning_plan_terminal_response(tool_event: dict) -> str | None:
    try:
        result = json.loads(tool_event["result"])
    except json.JSONDecodeError:
        return None
    plan_id = result.get("id")
    if tool_event.get("tool") == "propose_learning_plan":
        step_count = result.get("step_count", 0)
        return (
            f"Learning plan proposed — Plan ID: {plan_id}. "
            f"{step_count} step{'s' if step_count != 1 else ''} awaiting approval "
            "in Study Plan."
        )
    pending = result.get("pending_change_count", 0)
    return (
        f"Learning plan update proposed — Plan ID: {plan_id}. "
        f"{pending} pending change{'s' if pending != 1 else ''} awaiting approval "
        "in Study Plan."
    )
