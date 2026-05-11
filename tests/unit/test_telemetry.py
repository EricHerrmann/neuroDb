from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from neurodb.agents.db_agent import NeuroDbAgent
from neurodb.db import init_db
from neurodb.model_telemetry import build_model_call_log, record_model_call
from neurodb.schema import Base, ModelCallLog
from neurodb.session_manager import SessionManager


def _text_block(text: str = "ok"):
    return SimpleNamespace(type="text", text=text)


def _tool_block(name: str):
    return SimpleNamespace(type="tool_use", name=name)


def _usage(input_tokens: int = 10, output_tokens: int = 5):
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)


def _response(stop_reason: str = "end_turn", content=None, usage=None):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content if content is not None else [_text_block()],
        usage=usage,
    )


class _Stream:
    def __init__(self, events, final_message):
        self._events = events
        self._final_message = final_message

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._events)

    def get_final_message(self):
        return self._final_message


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_model_call_log_schema_created_by_metadata():
    engine = _engine()
    inspector = inspect(engine)
    assert "model_call_log" in inspector.get_table_names()


def test_model_call_log_schema_created_by_init_db():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    inspector = inspect(engine)
    assert "model_call_log" in inspector.get_table_names()


def test_build_model_call_log_extracts_usage_and_tool_names():
    response = _response(
        "tool_use",
        [_tool_block("query_db"), _tool_block("semantic_search")],
        _usage(123, 45),
    )

    row = build_model_call_log(
        task_type="agent.loop.local_db",
        provider="anthropic",
        model="claude-test",
        mode="local_db",
        response=response,
        iteration=2,
        elapsed_ms=37,
    )

    assert row.input_tokens == 123
    assert row.output_tokens == 45
    assert row.tool_name == "query_db"
    assert row.tool_names_json == '["query_db", "semantic_search"]'
    assert row.stop_reason == "tool_use"
    assert row.estimated_cost_usd is None


def test_build_model_call_log_allows_missing_usage():
    row = build_model_call_log(
        task_type="summary.session",
        provider="anthropic",
        model="claude-test",
        mode="summary",
        response=_response(),
        iteration=1,
        elapsed_ms=1,
    )

    assert row.input_tokens is None
    assert row.output_tokens is None


def test_record_model_call_writes_row():
    engine = _engine()
    record_model_call(
        engine,
        task_type="summary.session",
        provider="anthropic",
        model="claude-test",
        mode="summary",
        response=_response(usage=_usage(20, 10)),
        iteration=1,
        elapsed_ms=3,
    )

    with Session(engine) as session:
        row = session.query(ModelCallLog).one()
        assert row.task_type == "summary.session"
        assert row.input_tokens == 20
        assert row.output_tokens == 10


def test_record_model_call_failure_does_not_raise():
    record_model_call(
        object(),
        task_type="summary.session",
        provider="anthropic",
        model="claude-test",
        mode="summary",
        response=_response(),
        iteration=1,
        elapsed_ms=1,
    )


def test_agent_non_streaming_logs_model_call():
    engine = _engine()
    client = MagicMock()
    client.messages.create.return_value = _response(
        "end_turn",
        [_text_block("done")],
        _usage(30, 12),
    )
    agent = NeuroDbAgent(client, engine, mode="local_db", model="claude-test")

    assert "".join(agent.chat("hello", [])) == "done"

    with Session(engine) as session:
        row = session.query(ModelCallLog).one()
        assert row.task_type == "agent.loop.local_db"
        assert row.mode == "local_db"
        assert row.model == "claude-test"
        assert row.stop_reason == "end_turn"
        assert row.iteration == 1
        assert row.input_tokens == 30
        assert row.output_tokens == 12


def test_agent_telemetry_uses_routed_provider():
    engine = _engine()
    client = MagicMock()
    client.messages.create.return_value = _response(
        "end_turn",
        [_text_block("done")],
        _usage(30, 12),
    )
    agent = NeuroDbAgent(
        client,
        engine,
        mode="local_db",
        model="gpt-5-mini",
        model_provider="openai",
    )

    assert "".join(agent.chat("hello", [])) == "done"

    with Session(engine) as session:
        row = session.query(ModelCallLog).one()
        assert row.provider == "openai"
        assert row.model == "gpt-5-mini"


def test_agent_streaming_logs_model_call():
    engine = _engine()
    client = MagicMock()
    client.messages.stream.return_value = _Stream(
        [],
        _response("end_turn", [_text_block("done")], _usage(40, 14)),
    )
    agent = NeuroDbAgent(client, engine, mode="external_db", model="claude-test")

    events = list(agent.chat_stream("hello", []))
    assert events[-1]["type"] == "done"

    with Session(engine) as session:
        row = session.query(ModelCallLog).one()
        assert row.task_type == "agent.loop.external_db"
        assert row.mode == "external_db"
        assert row.iteration == 1
        assert row.input_tokens == 40
        assert row.output_tokens == 14


def test_agent_telemetry_failure_does_not_break_response():
    engine = _engine()
    client = MagicMock()
    client.messages.create.return_value = _response("end_turn", [_text_block("ok")])
    agent = NeuroDbAgent(client, engine)

    with patch("neurodb.agents.base.record_model_call", side_effect=RuntimeError("boom")):
        assert "".join(agent.chat("hello", [])) == "ok"


def test_session_summary_logs_model_call():
    engine = _engine()
    client = MagicMock()
    client.messages.create.return_value = _response(
        "end_turn",
        [_text_block("Topic: LTP\nDate: 2026-05-07")],
        _usage(50, 20),
    )
    manager = SessionManager(
        MagicMock(),
        client=client,
        date_provider=lambda: "2026-05-07",
        engine=engine,
    )

    summary = manager._generate_summary([{"role": "user", "content": "Discuss LTP"}])
    assert "LTP" in summary

    with Session(engine) as session:
        row = session.query(ModelCallLog).one()
        assert row.task_type == "summary.session"
        assert row.mode == "summary"
        assert row.input_tokens == 50
        assert row.output_tokens == 20
