from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

from neurodb.db import get_session, init_db
from neurodb.research.learning_plans import confirm_plan, dismiss_plan, get_plan, propose_plan
from neurodb.schema import Paper


@pytest.fixture(autouse=True)
def _no_matcher():
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
        {"type": "action", "action_text": "Summarize"},
    ]


def _paper_count(eng):
    with get_session(eng) as s:
        return s.execute(select(func.count()).select_from(Paper)).scalar_one()


def test_confirm_activates_and_resolves_read_paper():
    eng = _engine()
    pid = propose_plan(
        eng, title="P", origin_prompt="p", origin_agent="tutor", steps=_steps()
    )["id"]
    assert _paper_count(eng) == 0  # nothing queued at propose time
    confirm_plan(eng, pid)
    plan = get_plan(eng, pid)
    assert plan["status"] == "active"
    assert all(s["lifecycle"] == "confirmed" for s in plan["steps"])
    read = next(s for s in plan["steps"] if s["step_type"] == "read")
    assert read["paper_id"] is not None and read["source_ref"] is None
    assert read["source_title"] == "LTP Review"
    assert read["source_type"] == "paper"
    assert read["topic_context"] == "plasticity"
    assert _paper_count(eng) == 1


def test_get_plan_exposes_proposed_read_source_metadata():
    eng = _engine()
    pid = propose_plan(
        eng, title="P", origin_prompt="p", origin_agent="tutor", steps=_steps()
    )["id"]

    read = next(s for s in get_plan(eng, pid)["steps"] if s["step_type"] == "read")

    assert read["paper_id"] is None
    assert read["source_title"] == "LTP Review"
    assert read["source_type"] == "paper"
    assert read["topic_context"] == "plasticity"


def test_confirm_captures_read_source_abstract_tier():
    # A read-step source that carries an abstract must be captured at abstract
    # tier through the shared write path, not silently dropped to metadata.
    eng = _engine()
    steps = [{
        "type": "read",
        "source": {
            "title": "Engram review",
            "source_type": "review",
            "topic_context": "engrams",
            "abstract": "Engram cells encode memory traces.",
            "year": 2022,
        },
    }]
    pid = propose_plan(
        eng, title="P", origin_prompt="p", origin_agent="tutor", steps=steps
    )["id"]
    confirm_plan(eng, pid)
    with get_session(eng) as s:
        row = s.execute(select(Paper)).scalars().one()
        assert row.abstract == "Engram cells encode memory traces."
        assert row.year == 2022
        assert row.data_tier == "abstract"


def test_confirm_dedups_existing_paper():
    eng = _engine()
    # Two plans referencing the same source title -> one paper.
    p1 = propose_plan(eng, title="A", origin_prompt="a", origin_agent="tutor", steps=_steps())["id"]
    p2 = propose_plan(eng, title="B", origin_prompt="b", origin_agent="tutor", steps=_steps())["id"]
    confirm_plan(eng, p1)
    confirm_plan(eng, p2)
    assert _paper_count(eng) == 1


def test_dismiss_proposed_plan_leaves_no_papers():
    eng = _engine()
    pid = propose_plan(
        eng, title="P", origin_prompt="p", origin_agent="tutor", steps=_steps()
    )["id"]
    assert dismiss_plan(eng, pid) is True
    assert get_plan(eng, pid) is None
    assert _paper_count(eng) == 0
