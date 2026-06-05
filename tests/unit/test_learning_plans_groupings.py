from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.db import get_session, init_db
from neurodb.db.grouping_store import get_or_create_grouping, link_grouping
from neurodb.research.learning_plans import get_plan, plans_sharing_grouping, propose_plan


def _engine():
    eng = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    init_db(eng)
    return eng


def test_propose_runs_grouping_matcher():
    eng = _engine()
    with patch("neurodb.research.learning_plans.run_suggest_groupings") as mock_run:
        out = propose_plan(eng, title="Plasticity", origin_prompt="explain plasticity",
                           origin_agent="tutor", steps=[{"type": "action", "action_text": "x"}])
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["anchor_type"] == "learning_plan"
    assert kwargs["anchor_id"] == out["id"]
    assert kwargs["gtypes"] == ("topic", "concept")


def test_get_plan_includes_confirmed_groupings_and_cross_ref():
    eng = _engine()
    with patch("neurodb.research.learning_plans.run_suggest_groupings"):
        p1 = propose_plan(eng, title="A", origin_prompt="a", origin_agent="tutor",
                          steps=[{"type": "action", "action_text": "x"}])["id"]
        p2 = propose_plan(eng, title="B", origin_prompt="b", origin_agent="tutor",
                          steps=[{"type": "action", "action_text": "y"}])["id"]
    with get_session(eng) as s:
        g = get_or_create_grouping(s, "topic", "plasticity")
        link_grouping(s, g.id, "learning_plan", p1, status="confirmed")
        link_grouping(s, g.id, "learning_plan", p2, status="confirmed")
        s.commit()
        gid = g.id
    plan = get_plan(eng, p1)
    names = [grp["name"] for grp in plan["groupings"]]
    assert "plasticity" in names
    assert plans_sharing_grouping(eng, gid) == 2
