import pytest
from unittest.mock import MagicMock, patch

from neurodb.agents.db_agent import NeuroDbAgent


def _make_agent():
    return NeuroDbAgent(
        client=MagicMock(),
        engine=MagicMock(),
        vector_store=MagicMock(),
    )


def test_messages_rolled_back_on_tool_execution_exception():
    """If _execute_tool_block raises, api_messages must be rolled back to pre-call state."""
    agent = _make_agent()

    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "tu_001"
    tool_use_block.name = "list_datasets"
    tool_use_block.input = {}

    mock_response = MagicMock()
    mock_response.stop_reason = "tool_use"
    mock_response.content = [tool_use_block]

    agent._client.messages.create.return_value = mock_response

    messages = []

    with patch.object(agent, "_execute_tool_block", side_effect=RuntimeError("tool failed")):
        with pytest.raises(RuntimeError, match="tool failed"):
            list(agent.chat("test", messages))

    assert len(messages) == 0, (
        f"Expected messages to be rolled back on exception, got {len(messages)} entries"
    )


def test_messages_unchanged_before_any_api_call_on_exception():
    """If the first messages.create() raises, messages must be rolled back."""
    agent = _make_agent()
    agent._client.messages.create.side_effect = RuntimeError("network error")

    messages = []

    with pytest.raises(RuntimeError, match="network error"):
        list(agent.chat("test", messages))

    assert len(messages) == 0
