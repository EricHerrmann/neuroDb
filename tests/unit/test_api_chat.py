"""Tests for POST /chat/turn SSE streaming route."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.api.routes.chat import router


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine))


def _parse_sse_events(text: str) -> list[dict]:
    """Parse SSE lines from response text into a list of event dicts."""
    return [
        json.loads(line[6:])
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


def test_chat_turn_streams_done_event():
    """Mock agent.chat to yield 'hello'; confirm a done event with stop_reason='end_turn'."""
    client = _make_client()
    mock_agent = MagicMock()
    mock_agent.chat.return_value = iter(["hello"])
    with patch("neurodb.api.routes.chat._build_agent", return_value=mock_agent):
        with patch(
            "neurodb.api.routes.chat.build_provider_clients",
            return_value={"anthropic": MagicMock()},
        ):
            resp = client.post(
                "/api/chat/turn",
                json={"message": "hi", "history": [], "agent_mode": "local_db"},
            )
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(done_events) == 1
    assert done_events[0]["stop_reason"] == "end_turn"


def test_chat_turn_streams_text_delta_event():
    """Mock agent to yield 'chunk1'; confirm a text_delta event appears before done."""
    client = _make_client()
    mock_agent = MagicMock()
    mock_agent.chat.return_value = iter(["chunk1"])
    with patch("neurodb.api.routes.chat._build_agent", return_value=mock_agent):
        with patch(
            "neurodb.api.routes.chat.build_provider_clients",
            return_value={"anthropic": MagicMock()},
        ):
            resp = client.post(
                "/api/chat/turn",
                json={"message": "hi", "history": [], "agent_mode": "local_db"},
            )
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    text_delta_events = [e for e in events if e.get("type") == "text_delta"]
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(text_delta_events) >= 1
    assert text_delta_events[0]["text"] == "chunk1"
    # text_delta must appear before done
    assert events.index(text_delta_events[0]) < events.index(done_events[0])


def test_chat_turn_rejects_unknown_agent_mode():
    """POST with agent_mode='invalid' should return 400 before streaming."""
    client = _make_client()
    with patch(
        "neurodb.api.routes.chat.build_provider_clients",
        return_value={"anthropic": MagicMock()},
    ):
        resp = client.post(
            "/api/chat/turn",
            json={"message": "hi", "history": [], "agent_mode": "invalid"},
        )
    assert resp.status_code == 400


def test_chat_turn_returns_503_when_no_providers():
    """When build_provider_clients returns {}, expect 503 before streaming."""
    client = _make_client()
    with patch(
        "neurodb.api.routes.chat.build_provider_clients",
        return_value={},
    ):
        resp = client.post(
            "/api/chat/turn",
            json={"message": "hi", "history": [], "agent_mode": "local_db"},
        )
    assert resp.status_code == 503
