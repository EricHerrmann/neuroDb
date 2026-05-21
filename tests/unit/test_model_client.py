"""Tests for ModelClient ABC, normalized types, AnthropicModelClient, and OpenAIModelClient."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from neurodb.config.model_client import ContentBlock, ModelClient, ModelResponse


class _RetryableError(Exception):
    status_code = 500


# --- ContentBlock ---

def test_content_block_text_fields():
    block = ContentBlock(type="text", text="hello")
    assert block.type == "text"
    assert block.text == "hello"
    assert block.tool_name is None
    assert block.tool_use_id is None
    assert block.tool_input is None


def test_content_block_tool_use_fields():
    block = ContentBlock(
        type="tool_use",
        tool_name="run_query",
        tool_use_id="tu_abc",
        tool_input={"sql": "SELECT 1"},
    )
    assert block.type == "tool_use"
    assert block.tool_name == "run_query"
    assert block.tool_use_id == "tu_abc"
    assert block.tool_input == {"sql": "SELECT 1"}
    assert block.text is None


# --- ModelResponse ---

def test_model_response_constructs():
    block = ContentBlock(type="text", text="done")
    resp = ModelResponse(stop_reason="end_turn", content=[block])
    assert resp.stop_reason == "end_turn"
    assert len(resp.content) == 1
    assert resp.content[0].text == "done"


def test_model_response_default_content_is_empty_list():
    resp = ModelResponse(stop_reason="end_turn")
    assert resp.content == []


def test_model_response_carries_token_counts():
    resp = ModelResponse(stop_reason="end_turn", input_tokens=100, output_tokens=50)
    assert resp.input_tokens == 100
    assert resp.output_tokens == 50


# --- ModelClient ABC ---

def test_model_client_cannot_be_instantiated():
    with pytest.raises(TypeError):
        ModelClient()


def test_model_client_concrete_requires_all_abstract_methods():
    class Incomplete(ModelClient):
        def create_message(self, model, messages, system, tools, max_tokens):
            return ModelResponse(stop_reason="end_turn")
        # Missing stream_message, format_tool, format_tool_result

    with pytest.raises(TypeError):
        Incomplete()


# --- AnthropicModelClient ---

def test_anthropic_create_message_returns_model_response():
    from neurodb.config.providers.anthropic_client import AnthropicModelClient

    sdk_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="Hello")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    mock_client = MagicMock()
    mock_client.messages.create.return_value = sdk_response

    client = AnthropicModelClient(mock_client)
    response = client.create_message(
        model="claude-test",
        messages=[{"role": "user", "content": "hi"}],
        system="You are helpful.",
        tools=[],
        max_tokens=100,
    )

    assert isinstance(response, ModelResponse)
    assert response.stop_reason == "end_turn"
    assert len(response.content) == 1
    assert response.content[0].type == "text"
    assert response.content[0].text == "Hello"


def test_anthropic_create_message_maps_tool_use_block():
    from neurodb.config.providers.anthropic_client import AnthropicModelClient

    sdk_response = SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(type="tool_use", id="t1", name="query_db", input={"sql": "SELECT 1"}),
        ],
        usage=SimpleNamespace(input_tokens=20, output_tokens=8),
    )
    mock_client = MagicMock()
    mock_client.messages.create.return_value = sdk_response

    client = AnthropicModelClient(mock_client)
    response = client.create_message("m", [], "", [], 100)

    assert response.stop_reason == "tool_use"
    block = response.content[0]
    assert block.type == "tool_use"
    assert block.tool_name == "query_db"
    assert block.tool_use_id == "t1"
    assert block.tool_input == {"sql": "SELECT 1"}


def test_anthropic_create_message_carries_token_counts():
    from neurodb.config.providers.anthropic_client import AnthropicModelClient

    sdk_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[],
        usage=SimpleNamespace(input_tokens=321, output_tokens=123),
    )
    mock_client = MagicMock()
    mock_client.messages.create.return_value = sdk_response

    client = AnthropicModelClient(mock_client)
    response = client.create_message("m", [], "", [], 100)

    assert response.input_tokens == 321
    assert response.output_tokens == 123


def test_anthropic_create_message_retries_retryable_provider_error():
    from neurodb.config.providers.anthropic_client import AnthropicModelClient

    sdk_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="Hello after retry")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _RetryableError("Error code: 500"),
        sdk_response,
    ]

    client = AnthropicModelClient(mock_client)
    with patch("neurodb.config.providers.anthropic_client.sleep"):
        response = client.create_message("m", [], "", [], 100)

    assert response.content[0].text == "Hello after retry"
    assert mock_client.messages.create.call_count == 2


def test_anthropic_format_tool_passes_through_unchanged():
    from neurodb.config.providers.anthropic_client import AnthropicModelClient

    tool_def = {
        "name": "query_db",
        "description": "Run SQL",
        "input_schema": {"type": "object", "properties": {"sql": {"type": "string"}}},
    }
    client = AnthropicModelClient(MagicMock())
    assert client.format_tool(tool_def) == tool_def


def test_anthropic_format_tool_result_structure():
    from neurodb.config.providers.anthropic_client import AnthropicModelClient

    client = AnthropicModelClient(MagicMock())
    result = client.format_tool_result("tu_abc", "result text")

    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "tu_abc"
    assert result["content"][0]["text"] == "result text"


def test_anthropic_stream_message_retries_retryable_provider_error():
    from neurodb.config.providers.anthropic_client import AnthropicModelClient

    @contextmanager
    def stream_context():
        yield []

    mock_client = MagicMock()
    mock_client.messages.stream.side_effect = [
        _RetryableError("Error code: 500"),
        stream_context(),
    ]

    client = AnthropicModelClient(mock_client)
    with patch("neurodb.config.providers.anthropic_client.sleep"):
        with client.stream_message("m", [], "", [], 100):
            pass

    assert mock_client.messages.stream.call_count == 2


# --- OpenAIModelClient ---

def test_openai_format_tool_translates_input_schema():
    from neurodb.config.providers.openai_client import OpenAIModelClient

    tool_def = {
        "name": "query_db",
        "description": "Run SQL",
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
        },
    }
    client = OpenAIModelClient(MagicMock())
    formatted = client.format_tool(tool_def)

    assert "parameters" in formatted
    assert "input_schema" not in formatted
    assert formatted["parameters"]["type"] == "object"
    assert formatted["parameters"]["required"] == ["sql"]


def test_openai_format_tool_result_structure():
    from neurodb.config.providers.openai_client import OpenAIModelClient

    client = OpenAIModelClient(MagicMock())
    result = client.format_tool_result("call_abc", "result text")

    # Stored in Anthropic format for consistent message history;
    # _translate_messages converts to role=tool on the wire.
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "call_abc"
    assert result["content"][0]["text"] == "result text"


def test_openai_stop_reason_normalized_to_end_turn():
    from neurodb.config.providers.openai_client import OpenAIModelClient

    choice = SimpleNamespace(
        finish_reason="stop",
        message=SimpleNamespace(
            content="Hello",
            tool_calls=None,
        ),
    )
    sdk_response = SimpleNamespace(
        choices=[choice],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = sdk_response

    client = OpenAIModelClient(mock_client)
    response = client.create_message("gpt-4o", [], "", [], 100)

    assert response.stop_reason == "end_turn"
    assert response.content[0].text == "Hello"


def test_openai_stop_reason_normalized_to_tool_use():
    from neurodb.config.providers.openai_client import OpenAIModelClient

    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="query_db", arguments='{"sql": "SELECT 1"}'),
    )
    choice = SimpleNamespace(
        finish_reason="tool_calls",
        message=SimpleNamespace(
            content=None,
            tool_calls=[tool_call],
        ),
    )
    sdk_response = SimpleNamespace(
        choices=[choice],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=8),
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = sdk_response

    client = OpenAIModelClient(mock_client)
    response = client.create_message("gpt-4o", [], "", [], 100)

    assert response.stop_reason == "tool_use"
    assert response.content[0].type == "tool_use"
    assert response.content[0].tool_name == "query_db"
    assert response.content[0].tool_input == {"sql": "SELECT 1"}
