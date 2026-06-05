import json
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.db import init_db
from neurodb.research.learning_plans import get_plan, list_plans, propose_plan


@pytest.fixture(autouse=True)
def _no_matcher():
    # propose_plan triggers the grouping matcher (provider-backed); keep unit
    # tests hermetic and fast by stubbing it.
    with patch("neurodb.research.learning_plans.run_suggest_groupings"):
        yield


def _engine():
    eng = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    init_db(eng)
    return eng


def _steps():
    return [
        {
            "type": "read",
            "source": {
                "title": "LTP Review", "source_type": "paper", "topic_context": "plasticity",
            },
        },
        {"type": "action", "action_text": "Summarize the mechanism"},
    ]


def test_propose_persists_proposed_plan_and_steps():
    eng = _engine()
    out = propose_plan(eng, title="Plasticity primer", origin_prompt="explain plasticity",
                       origin_agent="tutor", steps=_steps())
    plan = get_plan(eng, out["id"])
    assert plan["status"] == "proposed"
    assert len(plan["steps"]) == 2
    assert all(s["lifecycle"] == "proposed" for s in plan["steps"])
    read = next(s for s in plan["steps"] if s["step_type"] == "read")
    assert read["paper_id"] is None
    assert json.loads(read["source_ref"])["title"] == "LTP Review"
    assert plan["steps"][0]["order_index"] == 0 and plan["steps"][1]["order_index"] == 1


def test_list_plans_filters_by_status():
    eng = _engine()
    propose_plan(eng, title="A", origin_prompt="a", origin_agent="tutor", steps=_steps())
    assert len(list_plans(eng, status="proposed")) == 1
    assert list_plans(eng, status="active") == []


def test_percent_complete_zero_for_new_plan():
    eng = _engine()
    out = propose_plan(eng, title="A", origin_prompt="a", origin_agent="research", steps=_steps())
    assert get_plan(eng, out["id"])["percent_complete"] == 0
