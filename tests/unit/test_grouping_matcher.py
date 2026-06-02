"""Unit tests for suggest_groupings with a fake ModelClient (Groupings Phase 3a)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.config.model_client import ContentBlock, ModelResponse
from neurodb.db.grouping_store import get_or_create_grouping, set_parent
from neurodb.research.grouping_matcher import suggest_groupings


def _now():
    return datetime.now(timezone.utc).isoformat()


class FakeClient:
    """Duck-typed ModelClient returning a single submit_groupings tool call."""

    def __init__(self, tool_input):
        self._tool_input = tool_input
        self.calls = []

    def format_tool(self, tool_definition):
        return tool_definition

    def create_message(self, *, model, messages, system, tools, max_tokens, tool_choice=None):
        self.calls.append({"model": model, "tool_choice": tool_choice})
        return ModelResponse(
            stop_reason="tool_use",
            content=[ContentBlock(type="tool_use", tool_name="submit_groupings",
                                  tool_input=self._tool_input)],
            input_tokens=12, output_tokens=8,
        )


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def _run(engine, client, gtype="topic"):
    return suggest_groupings(
        engine, anchor_type="question", anchor_id=1, anchor_text="some text",
        gtype=gtype, model_client=client, model="fake-model",
        model_provider="anthropic", max_tokens=1024,
    )


def _links(engine):
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT grouping_id, anchor_type, anchor_id, status FROM grouping_links"
        )).fetchall()


def test_relevant_existing_creates_pending_links(engine):
    with Session(engine) as s:
        g = get_or_create_grouping(s, "topic", "stroke")
        s.commit()
        gid = g.id
    client = FakeClient({"relevant_existing": [{"id": gid, "reason": "match"}], "proposed_new": []})
    out = _run(engine, client)
    assert out["suggested"] == ["stroke"]
    assert (gid, "question", 1, "pending") in _links(engine)


def test_child_match_rolls_up_to_parent(engine):
    with Session(engine) as s:
        parent = get_or_create_grouping(s, "topic", "plasticity")
        child = get_or_create_grouping(s, "topic", "neuroplasticity")
        set_parent(s, child.id, parent.id)
        s.commit()
        parent_id, child_id = parent.id, child.id
    client = FakeClient({"relevant_existing": [{"id": child_id, "reason": "m"}], "proposed_new": []})
    out = _run(engine, client)
    rows = {(r[0], r[3]) for r in _links(engine)}
    assert (child_id, "pending") in rows
    assert (parent_id, "pending") in rows  # rolled up
    assert "plasticity" in out["suggested"]


def test_proposed_new_creates_proposed_grouping(engine):
    client = FakeClient({"relevant_existing": [],
                         "proposed_new": [{"name": "plasticity", "parent_name": None}]})
    out = _run(engine, client)
    assert out["proposed"] == ["plasticity"]
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT status FROM groupings WHERE type='topic' AND name='plasticity'"
        )).fetchone()
    assert row[0] == "proposed"
    assert len(_links(engine)) == 1


def test_proposed_name_matching_existing_active_links_instead_of_duplicating(engine):
    with Session(engine) as s:
        g = get_or_create_grouping(s, "topic", "stroke")  # active
        s.commit()
        gid = g.id
    client = FakeClient({"relevant_existing": [],
                         "proposed_new": [{"name": "stroke", "parent_name": None}]})
    out = _run(engine, client)
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM groupings WHERE name='stroke'")).fetchone()[0]
    assert n == 1                      # no duplicate
    assert out["proposed"] == []       # treated as existing
    assert (gid, "question", 1, "pending") in _links(engine)


def test_invalid_existing_id_is_ignored(engine):
    client = FakeClient({"relevant_existing": [{"id": 99999, "reason": "ghost"}], "proposed_new": []})
    out = _run(engine, client)
    assert out["suggested"] == []
    assert _links(engine) == []


def test_run_suggest_groupings_fails_closed(engine, monkeypatch):
    from sqlalchemy import text as _text
    from neurodb.research import grouping_matcher
    import neurodb.config.provider_factory as pf

    # No providers configured → TaskRouter.route raises RoutingError.
    monkeypatch.setattr(pf, "build_provider_clients", lambda: {})

    grouping_matcher.run_suggest_groupings(
        engine, anchor_type="question", anchor_id=1, anchor_text="x", gtypes=("topic",)
    )

    with engine.connect() as conn:
        links = conn.execute(_text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
        warnings = conn.execute(_text(
            "SELECT COUNT(*) FROM system_warnings WHERE warning_type='grouping_match_failed'"
        )).fetchone()[0]
    assert links == 0
    assert warnings >= 1
