"""OpenAIModelClient — wraps the OpenAI SDK as a ModelClient (Groq-compatible)."""
from __future__ import annotations

import json
from contextlib import contextmanager
from time import sleep

from neurodb.config.model_client import ContentBlock, ModelClient, ModelResponse

_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
_RETRY_DELAYS_SECONDS = (0.25, 0.75)


class OpenAIModelClient(ModelClient):
    """Adapter for the OpenAI SDK. Also works with Groq via base_url override."""

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
        oai_messages = _translate_messages(messages, system)
        oai_tools = [self.format_tool(t) for t in tools] if tools else None
        kwargs: dict = dict(model=model, messages=oai_messages, max_completion_tokens=max_tokens)
        if oai_tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in oai_tools]
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        response = _call_with_retries(self._client.chat.completions.create, **kwargs)
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
        oai_messages = _translate_messages(messages, system)
        oai_tools = [self.format_tool(t) for t in tools] if tools else None
        kwargs: dict = dict(model=model, messages=oai_messages, max_completion_tokens=max_tokens, stream=True, stream_options={"include_usage": True})
        if oai_tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in oai_tools]

        stream = _call_with_retries(self._client.chat.completions.create, **kwargs)
        yield _OpenAIStream(stream)

    def format_tool(self, tool_definition: dict) -> dict:
        """Translate Anthropic input_schema format to OpenAI parameters format."""
        result = dict(tool_definition)
        if "input_schema" in result:
            result["parameters"] = result.pop("input_schema")
        return result

    def format_tool_result(self, tool_use_id: str, content: str) -> dict:
        # Return Anthropic-format so message history is stored consistently.
        # _translate_messages unpacks these into role=tool wire messages.
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


class _OpenAIStream:
    """Wraps an OpenAI streaming response as a ModelStream."""

    def __init__(self, stream) -> None:
        self._stream = stream
        self._chunks: list = []

    def __iter__(self):
        for chunk in self._stream:
            self._chunks.append(chunk)
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue
            delta = getattr(choice, "delta", None)
            if delta and getattr(delta, "content", None):
                yield {"type": "text_delta", "text": delta.content}

    def get_final_message(self) -> ModelResponse:
        # Reconstruct from accumulated chunks
        text_parts: list[str] = []
        tool_calls: dict[int, dict] = {}
        finish_reason = "stop"
        prompt_tokens = None
        completion_tokens = None

        for chunk in self._chunks:
            if hasattr(chunk, "usage") and chunk.usage:
                prompt_tokens = getattr(chunk.usage, "prompt_tokens", None)
                completion_tokens = getattr(chunk.usage, "completion_tokens", None)
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue
            if getattr(delta, "content", None):
                text_parts.append(delta.content)
            if getattr(delta, "tool_calls", None):
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls[idx]["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn:
                        if getattr(fn, "name", None):
                            tool_calls[idx]["name"] += fn.name
                        if getattr(fn, "arguments", None):
                            tool_calls[idx]["arguments"] += fn.arguments

        return _build_response(text_parts, tool_calls, finish_reason, prompt_tokens, completion_tokens)


def _map_response(sdk_response) -> ModelResponse:
    choice = sdk_response.choices[0]
    message = choice.message
    finish_reason = choice.finish_reason

    text_parts: list[str] = []
    tool_calls: dict[int, dict] = {}

    if getattr(message, "content", None):
        text_parts.append(message.content)

    if getattr(message, "tool_calls", None):
        for idx, tc in enumerate(message.tool_calls):
            tool_calls[idx] = {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            }

    usage = getattr(sdk_response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

    return _build_response(text_parts, tool_calls, finish_reason, prompt_tokens, completion_tokens)


def _build_response(
    text_parts: list[str],
    tool_calls: dict[int, dict],
    finish_reason: str,
    prompt_tokens,
    completion_tokens,
) -> ModelResponse:
    blocks: list[ContentBlock] = []
    text = "".join(text_parts)
    if text:
        blocks.append(ContentBlock(type="text", text=text))

    for tc in sorted(tool_calls.values(), key=lambda x: list(tool_calls.values()).index(x)):
        try:
            inputs = json.loads(tc["arguments"]) if tc["arguments"] else {}
        except json.JSONDecodeError:
            inputs = {}
        blocks.append(ContentBlock(
            type="tool_use",
            tool_name=tc["name"],
            tool_use_id=tc["id"],
            tool_input=inputs,
        ))

    stop_reason = _normalize_stop_reason(finish_reason)
    return ModelResponse(
        stop_reason=stop_reason,
        content=blocks,
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
    )


def _normalize_stop_reason(finish_reason: str) -> str:
    if finish_reason == "stop":
        return "end_turn"
    if finish_reason == "tool_calls":
        return "tool_use"
    if finish_reason == "length":
        return "max_tokens"
    return "end_turn"


def _translate_messages(messages: list[dict], system: str) -> list[dict]:
    """Convert Anthropic-format message history to OpenAI format."""
    result: list[dict] = []
    if system:
        result.append({"role": "system", "content": system})
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "assistant":
            result.append(_translate_assistant_message(content))
        elif role == "user":
            if isinstance(content, list):
                # Check if this is a tool_result batch
                if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                    for tr in content:
                        text = ""
                        tr_content = tr.get("content", [])
                        if isinstance(tr_content, list) and tr_content:
                            text = tr_content[0].get("text", "")
                        elif isinstance(tr_content, str):
                            text = tr_content
                        result.append({
                            "role": "tool",
                            "tool_call_id": tr.get("tool_use_id", ""),
                            "content": text,
                        })
                    continue
            result.append({"role": "user", "content": content if isinstance(content, str) else str(content)})
        else:
            result.append(msg)

    return result


def _translate_assistant_message(content) -> dict:
    """Convert Anthropic assistant content blocks to OpenAI assistant message."""
    if isinstance(content, str):
        return {"role": "assistant", "content": content}
    if not isinstance(content, list):
        return {"role": "assistant", "content": str(content)}

    text_parts = []
    tool_calls = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                import json as _json
                tool_calls.append({
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": _json.dumps(block.get("input", {})),
                    },
                })

    msg: dict = {"role": "assistant"}
    if text_parts:
        msg["content"] = "".join(text_parts)
    else:
        msg["content"] = None
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg
