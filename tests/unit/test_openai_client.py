"""Tests for OpenAIModelClient — verifies SDK call translation."""
from unittest.mock import MagicMock, patch

import pytest

from neurodb.config.providers.openai_client import OpenAIModelClient


def _make_client():
    """Return an OpenAIModelClient with a mock underlying SDK client."""
    mock_sdk = MagicMock()
    return OpenAIModelClient(mock_sdk), mock_sdk


def _make_completion(text="hello", finish_reason="stop"):
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason
    response = MagicMock()
    response.choices = [choice]
    response.usage = None
    return response


class _RetryableError(Exception):
    status_code = 500


def test_create_message_uses_max_completion_tokens():
    client, mock_sdk = _make_client()
    mock_sdk.chat.completions.create.return_value = _make_completion()

    client.create_message(
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": "hi"}],
        system="you are helpful",
        tools=[],
        max_tokens=512,
    )

    call_kwargs = mock_sdk.chat.completions.create.call_args[1]
    assert "max_completion_tokens" in call_kwargs
    assert call_kwargs["max_completion_tokens"] == 512
    assert "max_tokens" not in call_kwargs


def test_create_message_retries_retryable_provider_error():
    client, mock_sdk = _make_client()
    mock_sdk.chat.completions.create.side_effect = [
        _RetryableError("Error code: 500"),
        _make_completion(),
    ]

    with patch("neurodb.config.providers.openai_client.sleep"):
        response = client.create_message(
            model="gpt-5.4-mini",
            messages=[{"role": "user", "content": "hi"}],
            system="you are helpful",
            tools=[],
            max_tokens=512,
        )

    assert response.content[0].text == "hello"
    assert mock_sdk.chat.completions.create.call_count == 2


def test_stream_message_uses_max_completion_tokens():
    client, mock_sdk = _make_client()
    mock_sdk.chat.completions.create.return_value = iter([])

    with client.stream_message(
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": "hi"}],
        system="you are helpful",
        tools=[],
        max_tokens=512,
    ):
        pass

    call_kwargs = mock_sdk.chat.completions.create.call_args[1]
    assert "max_completion_tokens" in call_kwargs
    assert call_kwargs["max_completion_tokens"] == 512
    assert "max_tokens" not in call_kwargs


def test_stream_message_retries_retryable_provider_error():
    client, mock_sdk = _make_client()
    mock_sdk.chat.completions.create.side_effect = [
        _RetryableError("Error code: 500"),
        iter([]),
    ]

    with patch("neurodb.config.providers.openai_client.sleep"):
        with client.stream_message(
            model="gpt-5.4-mini",
            messages=[{"role": "user", "content": "hi"}],
            system="you are helpful",
            tools=[],
            max_tokens=512,
        ):
            pass

    assert mock_sdk.chat.completions.create.call_count == 2


def test_format_tool_result_returns_anthropic_format():
    # Tool results must be stored in Anthropic format so _translate_messages
    # can detect and unpack them as role=tool messages on the wire.
    client, _ = _make_client()

    result = client.format_tool_result("call_abc123", "42 datasets")

    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "call_abc123"
    assert isinstance(result["content"], list)
    assert result["content"][0]["text"] == "42 datasets"


def test_translate_messages_unpacks_tool_results_as_role_tool():
    # A round-trip: history with an assistant tool_use block followed by a
    # user message containing Anthropic-format tool results must arrive at
    # the SDK as separate role=tool messages (not a stringified user message).
    client, mock_sdk = _make_client()
    mock_sdk.chat.completions.create.return_value = _make_completion()

    messages = [
        {"role": "user", "content": "How many datasets?"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "call_abc123", "name": "query_db", "input": {"sql": "SELECT 1"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_abc123",
             "content": [{"type": "text", "text": "42 datasets"}]},
        ]},
    ]

    client.create_message(
        model="gpt-5.4-mini",
        messages=messages,
        system="",
        tools=[],
        max_tokens=512,
    )

    sent = mock_sdk.chat.completions.create.call_args[1]["messages"]
    tool_msg = next((m for m in sent if m.get("role") == "tool"), None)
    assert tool_msg is not None, "No role=tool message sent to SDK"
    assert tool_msg["tool_call_id"] == "call_abc123"
    assert tool_msg["content"] == "42 datasets"
    # Must not appear as a plain user message
    user_msgs = [m for m in sent if m.get("role") == "user"]
    for um in user_msgs:
        assert "tool_result" not in str(um.get("content", ""))
