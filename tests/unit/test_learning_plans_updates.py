from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.db import init_db
from neurodb.research.learning_plans import (
    confirm_pending_changes,
    confirm_plan,
    delete_plan,
    dismiss_pending_changes,
    get_plan,
    propose_plan,
    propose_plan_update,
    set_step_progress,
    update_plan,
)


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


def _active_plan(eng):
    pid = propose_plan(eng, title="P", origin_prompt="p", origin_agent="research",
                       steps=[{"type": "action", "action_text": "first"}])["id"]
    confirm_plan(eng, pid)
    return pid


def test_propose_update_adds_proposed_step_without_touching_active():
    eng = _engine()
    pid = _active_plan(eng)
    propose_plan_update(eng, plan_id=pid, add_steps=[{"type": "action", "action_text": "second"}])
    plan = get_plan(eng, pid)
    assert plan["pending_change_count"] == 1
    confirmed = [s for s in plan["steps"] if s["lifecycle"] == "confirmed"]
    proposed = [s for s in plan["steps"] if s["lifecycle"] == "proposed"]
    assert len(confirmed) == 1 and len(proposed) == 1


def test_propose_removal_then_confirm_changes_deletes_step():
    eng = _engine()
    pid = _active_plan(eng)
    step_id = get_plan(eng, pid)["steps"][0]["id"]
    propose_plan_update(eng, plan_id=pid, remove_step_ids=[step_id])
    assert get_plan(eng, pid)["steps"][0]["lifecycle"] == "proposed_removal"
    confirm_pending_changes(eng, pid)
    assert get_plan(eng, pid)["steps"] == []


def test_dismiss_changes_reverts_removal_and_drops_additions():
    eng = _engine()
    pid = _active_plan(eng)
    step_id = get_plan(eng, pid)["steps"][0]["id"]
    propose_plan_update(eng, plan_id=pid, add_steps=[{"type": "action", "action_text": "x"}],
                        remove_step_ids=[step_id])
    dismiss_pending_changes(eng, pid)
    plan = get_plan(eng, pid)
    assert len(plan["steps"]) == 1 and plan["steps"][0]["lifecycle"] == "confirmed"


def test_step_progress_drives_percent_complete():
    eng = _engine()
    pid = _active_plan(eng)
    step_id = get_plan(eng, pid)["steps"][0]["id"]
    set_step_progress(eng, step_id, "done")
    assert get_plan(eng, pid)["percent_complete"] == 100


def test_update_and_delete_plan():
    eng = _engine()
    pid = _active_plan(eng)
    update_plan(eng, pid, title="Renamed", status="paused")
    plan = get_plan(eng, pid)
    assert plan["title"] == "Renamed" and plan["status"] == "paused"
    assert delete_plan(eng, pid) is True
    assert get_plan(eng, pid) is None
