"""AnthropicModelClient — wraps the Anthropic SDK as a ModelClient."""
from __future__ import annotations

from contextlib import contextmanager
from time import sleep

from neurodb.config.model_client import ContentBlock, ModelClient, ModelResponse, ModelStream

_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
_RETRY_DELAYS_SECONDS = (0.25, 0.75)


class AnthropicModelClient(ModelClient):
    """Adapter that wraps an Anthropic SDK client instance."""

    def __init__(self, client) -> None:
        self._client = client

    def create_message(
        self,
        model: str,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int,
        tool_choice: str | None = None,
    ) -> ModelResponse:
        kwargs: dict = dict(model=model, max_tokens=max_tokens, system=system, tools=tools, messages=messages)
        if tool_choice == "required":
            kwargs["tool_choice"] = {"type": "any"}
        response = _call_with_retries(self._client.messages.create, **kwargs)
        return _map_response(response)

    @contextmanager
    def stream_message(
        self,
        model: str,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int,
    ):
        raw_context = _call_with_retries(
            self._client.messages.stream,
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        with raw_context as raw_stream:
            yield _AnthropicStream(raw_stream)

    def format_tool(self, tool_definition: dict) -> dict:
        return tool_definition

    def format_tool_result(self, tool_use_id: str, content: str) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [{"type": "text", "text": content}],
        }


def _call_with_retries(fn, **kwargs):
    last_exc = None
    for attempt in range(len(_RETRY_DELAYS_SECONDS) + 1):
        try:
            return fn(**kwargs)
        except Exception as exc:
            last_exc = exc
            if not _is_retryable_error(exc) or attempt >= len(_RETRY_DELAYS_SECONDS):
                raise
            sleep(_RETRY_DELAYS_SECONDS[attempt])
    raise last_exc


def _is_retryable_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in _RETRYABLE_STATUS_CODES:
        return True
    message = str(exc)
    return any(f"Error code: {code}" in message for code in _RETRYABLE_STATUS_CODES)


class _AnthropicStream:
    """Wraps an Anthropic SDK stream as a ModelStream."""

    def __init__(self, raw_stream) -> None:
        self._raw = raw_stream

    def __iter__(self):
        for event in self._raw:
            if (
                _get(event, "type") == "content_block_delta"
                and _get(_get(event, "delta"), "type") == "text_delta"
            ):
                yield {"type": "text_delta", "text": _get(_get(event, "delta"), "text")}

    def get_final_message(self) -> ModelResponse:
        return _map_response(self._raw.get_final_message())


def _map_response(sdk_response) -> ModelResponse:
    """Convert an Anthropic SDK response to a normalized ModelResponse."""
    content = _get(sdk_response, "content") or []
    blocks: list[ContentBlock] = []
    for block in content:
        block_type = _get(block, "type")
        if block_type == "text":
            blocks.append(ContentBlock(type="text", text=_get(block, "text")))
        elif block_type == "tool_use":
            blocks.append(ContentBlock(
                type="tool_use",
                tool_name=_get(block, "name"),
                tool_use_id=_get(block, "id"),
                tool_input=_get(block, "input") or {},
            ))

    usage = _get(sdk_response, "usage")
    input_tokens = _get(usage, "input_tokens") if usage else None
    output_tokens = _get(usage, "output_tokens") if usage else None

    return ModelResponse(
        stop_reason=_get(sdk_response, "stop_reason") or "end_turn",
        content=blocks,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _get(obj, name: str):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
