import json
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.db import init_db
from neurodb.agents.learning_plan_tools import (
    LEARNING_PLAN_TOOLS, execute_propose_learning_plan, execute_update_learning_plan,
)
from neurodb.research.learning_plans import get_plan


@pytest.fixture(autouse=True)
def _no_matcher():
    with patch("neurodb.research.learning_plans.run_suggest_groupings"):
        yield


def _engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(eng)
    return eng


def test_tool_schemas_present_and_groq_safe():
    names = {t["name"] for t in LEARNING_PLAN_TOOLS}
    assert names == {"propose_learning_plan", "update_learning_plan"}
    for tool in LEARNING_PLAN_TOOLS:
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema and "required" in schema


def test_execute_propose_persists_proposed_plan():
    eng = _engine()
    out = json.loads(execute_propose_learning_plan(eng, {
        "title": "P", "origin_prompt": "p", "origin_agent": "tutor",
        "steps": [{"type": "action", "action_text": "x"}],
    }))
    assert get_plan(eng, out["id"])["status"] == "proposed"
