from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from neurodb.agents.base import BaseAgent


class _ConcreteAgent(BaseAgent):
    def _get_active_tools(self):
        return []

    def _build_system_prompt(self):
        return "You are a test agent."

    def _execute_tool_block(self, block):
        return '{"ok": true}'


def _make_agent():
    return _ConcreteAgent(
        client=MagicMock(),
        engine=MagicMock(),
        vector_store=None,
        model="claude-test",
        prior_context="",
    )


def test_base_agent_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseAgent(MagicMock(), MagicMock(), None, "model", "")


def test_concrete_subclass_instantiates():
    assert _make_agent() is not None


def test_concrete_subclass_has_chat_method():
    assert callable(_make_agent().chat)


def test_concrete_subclass_has_chat_stream_method():
    assert callable(_make_agent().chat_stream)


def test_chat_rollback_on_exception():
    agent = _make_agent()
    tool_block = SimpleNamespace(type="tool_use", id="t1", name="test_tool", input={})
    agent._client.messages.create.return_value = SimpleNamespace(
        stop_reason="tool_use",
        content=[tool_block],
    )

    messages = []
    with patch.object(agent, "_execute_tool_block", side_effect=RuntimeError("fail")):
        with pytest.raises(RuntimeError, match="fail"):
            list(agent.chat("test", messages))

    assert messages == []


def test_chat_yields_text_on_end_turn():
    agent = _make_agent()
    agent._client.messages.create.return_value = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="Hello from agent")],
    )

    chunks = list(agent.chat("hi", []))
    assert "".join(chunks) == "Hello from agent"


def test_chat_stream_rolls_back_on_exception():
    agent = _make_agent()
    agent._client.messages.stream.side_effect = RuntimeError("network error")

    messages = []
    with pytest.raises(RuntimeError, match="network error"):
        list(agent.chat_stream("hi", messages))

    assert messages == []

