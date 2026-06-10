"""Tests for POST /chat/turn SSE streaming route."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.chat import router
from neurodb.schema import Base


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.state.chunk_store = None
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


def test_chat_turn_streams_tool_activity_events():
    client = _make_client()

    class StreamingAgent:
        def chat_stream(self, message, history):
            yield {"type": "tool_start", "tool_name": "query_db", "tool_input": {"sql": "SELECT 1"}}
            yield {"type": "tool_result", "tool_name": "query_db", "result": "[{\"x\": 1}]"}
            yield {"type": "done", "text": "Done", "stop_reason": "end_turn"}

    with patch("neurodb.api.routes.chat._build_agent", return_value=StreamingAgent()):
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
    assert [event["type"] for event in events] == ["tool_start", "tool_result", "done"]
    assert events[0]["tool_name"] == "query_db"


def test_chat_turn_streams_error_event_when_agent_stream_raises():
    client = _make_client()

    class FailingStreamingAgent:
        def chat_stream(self, message, history):
            yield {"type": "context_summary", "context_mode": "contextual"}
            raise RuntimeError("provider stream failed")

    with patch("neurodb.api.routes.chat._build_agent", return_value=FailingStreamingAgent()):
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
    assert [event["type"] for event in events] == ["context_summary", "error"]
    assert "provider stream failed" in events[-1]["text"]


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


def test_build_agent_passes_chroma_stores_to_research_agent():
    from neurodb.api.routes.chat import _build_agent

    route = SimpleNamespace(
        model_client=object(),
        model_id="research-model",
        provider="anthropic",
        max_tokens=2048,
    )

    with (
        patch("neurodb.api.routes.chat.TaskRouter") as router_cls,
        patch("neurodb.api.routes.chat.NeuroResearchAgent") as agent_cls,
    ):
        router_cls.return_value.route.return_value = route
        agent = _build_agent(
            "neuro_research",
            engine="engine",
            vector_store="vector-store",
            knowledge_store="knowledge-store",
            context_store="context-store",
            providers={"anthropic": object()},
            prior_context="prior",
            context_mode="grounded",
            context_bundle={"mode": "grounded"},
        )

    router_cls.return_value.route.assert_called_once_with("agent.loop.neuro_research", engine="engine")
    agent_cls.assert_called_once_with(
        model_client=route.model_client,
        model="research-model",
        max_tokens=2048,
        engine="engine",
        vector_store="vector-store",
        knowledge_store="knowledge-store",
        chunk_store=None,
        context_store="context-store",
        prior_context="prior",
        model_provider="anthropic",
        context_mode="grounded",
        context_bundle={"mode": "grounded"},
    )
    assert agent == agent_cls.return_value


def test_build_agent_preserves_external_db_mode():
    from neurodb.api.routes.chat import _build_agent

    route = SimpleNamespace(
        model_client=object(),
        model_id="db-model",
        provider="anthropic",
        max_tokens=2048,
    )

    with (
        patch("neurodb.api.routes.chat.TaskRouter") as router_cls,
        patch("neurodb.api.routes.chat.NeuroDbAgent") as agent_cls,
    ):
        router_cls.return_value.route.return_value = route
        agent = _build_agent(
            "external_db",
            engine="engine",
            vector_store="vector-store",
            knowledge_store="knowledge-store",
            context_store="context-store",
            providers={"anthropic": object()},
            prior_context="prior",
            context_mode="general",
            context_bundle={"mode": "general"},
        )

    router_cls.return_value.route.assert_called_once_with("agent.loop.external_db", engine="engine")
    agent_cls.assert_called_once_with(
        model_client=route.model_client,
        model="db-model",
        max_tokens=2048,
        engine="engine",
        vector_store="vector-store",
        mode="external_db",
        prior_context="prior",
        model_provider="anthropic",
    )
    assert agent == agent_cls.return_value


def test_chat_turn_passes_context_store_to_agent_builder():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = "vector-store"
    app.state.knowledge_store = "knowledge-store"
    app.state.context_store = "context-store"
    app.state.chunk_store = None
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    mock_agent = MagicMock()
    mock_agent.chat.return_value = iter(["hello"])
    providers = {"anthropic": MagicMock()}
    with patch("neurodb.api.routes.chat._build_agent", return_value=mock_agent) as build_agent:
        with patch("neurodb.api.routes.chat.build_provider_clients", return_value=providers):
            resp = client.post(
                "/api/chat/turn",
                json={"message": "hi", "history": [], "agent_mode": "neuro_research"},
            )

    assert resp.status_code == 200
    build_agent.assert_called_once_with(
        "neuro_research",
        engine,
        "vector-store",
        "knowledge-store",
        "context-store",
        providers,
        "",
        "contextual",
        ANY,
        chunk_store=None,
    )


def test_chat_turn_rejects_unknown_context_mode():
    client = _make_client()
    with patch(
        "neurodb.api.routes.chat.build_provider_clients",
        return_value={"anthropic": MagicMock()},
    ):
        resp = client.post(
            "/api/chat/turn",
            json={
                "message": "hi",
                "history": [],
                "agent_mode": "neuro_tutor",
                "context_mode": "strict",
            },
        )
    assert resp.status_code == 400


def test_chat_turn_passes_request_context_mode_and_focus_to_bundle_builder():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = "vector-store"
    app.state.knowledge_store = "knowledge-store"
    app.state.context_store = "context-store"
    app.state.chunk_store = None
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    mock_agent = MagicMock()
    mock_agent.chat.return_value = iter(["hello"])
    providers = {"anthropic": MagicMock()}
    context_bundle = {"mode": "grounded", "source_counts": {}, "warnings": []}
    with patch("neurodb.api.routes.chat._build_agent", return_value=mock_agent):
        with patch("neurodb.api.routes.chat.build_provider_clients", return_value=providers):
            with patch(
                "neurodb.api.routes.chat.build_context_bundle",
                return_value=context_bundle,
            ) as build_bundle:
                resp = client.post(
                    "/api/chat/turn",
                    json={
                        "message": "hi",
                        "history": [],
                        "agent_mode": "neuro_research",
                        "context_mode": "grounded",
                        "active_focus_type": "research_question",
                        "active_focus_id": 7,
                    },
                )

    assert resp.status_code == 200
    build_bundle.assert_called_once()
    assert build_bundle.call_args.kwargs["request"] == {
        "mode": "grounded",
        "agent_mode": "neuro_research",
        "user_message": "hi",
        "active_focus": {"focus_type": "research_question", "focus_id": 7},
    }
