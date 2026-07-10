"""Tests for the in-process event emitter."""
from __future__ import annotations

import logging

import pytest

from neurodb import events


@pytest.fixture(autouse=True)
def _clean_registry():
    events.reset()
    yield
    events.reset()


def test_emit_dispatches_to_all_handlers_with_payload():
    seen: list[tuple[str, int]] = []
    events.subscribe("thing_happened", lambda source_id: seen.append(("a", source_id)),
                     key="a")
    events.subscribe("thing_happened", lambda source_id: seen.append(("b", source_id)),
                     key="b")
    outcomes = events.emit("thing_happened", source_id=7)
    assert seen == [("a", 7), ("b", 7)]
    assert [o["status"] for o in outcomes] == ["ok", "ok"]


def test_handler_error_is_isolated_and_recorded(caplog):
    seen: list[int] = []

    def _boom(source_id):
        raise RuntimeError("kaput")

    events.subscribe("thing_happened", _boom, key="boom")
    events.subscribe("thing_happened", lambda source_id: seen.append(source_id),
                     key="ok")
    with caplog.at_level(logging.ERROR):
        outcomes = events.emit("thing_happened", source_id=1)
    assert seen == [1]  # second handler still ran
    assert outcomes[0] == {"handler": "boom", "status": "error", "error": "kaput"}
    assert "boom" in caplog.text  # not swallowed silently


def test_keyed_resubscribe_replaces_previous_handler():
    seen: list[str] = []
    events.subscribe("e", lambda: seen.append("old"), key="k")
    events.subscribe("e", lambda: seen.append("new"), key="k")
    events.emit("e")
    assert seen == ["new"]


def test_emit_with_no_subscribers_returns_empty():
    assert events.emit("nobody_listens", source_id=1) == []
