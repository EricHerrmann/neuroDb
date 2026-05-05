"""Abstract base class for NeuroDb agents."""
from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable

_DEFAULT_MODEL = "claude-opus-4-7"
_MAX_TURNS = 10


class BaseAgent(ABC):
    """Shared Anthropic tool-use loop for all NeuroDb agents."""

    def __init__(
        self,
        client,
        engine,
        vector_store=None,
        model: str = _DEFAULT_MODEL,
        prior_context: str = "",
    ) -> None:
        self._client = client
        self._engine = engine
        self._vector_store = vector_store
        self._model = model
        self.prior_context = prior_context

    @abstractmethod
    def _get_active_tools(self) -> list[dict]:
        """Return tool definitions available to this agent."""

    @abstractmethod
    def _build_system_prompt(self) -> str:
        """Return the system prompt for the current agent state."""

    @abstractmethod
    def _execute_tool_block(self, block) -> str:
        """Execute a Claude tool-use block and return text for tool_result."""

    def chat(self, user_message: str, messages: list[dict]) -> Generator[str, None, None]:
        """Run one user turn and rollback appended API messages on failure."""
        checkpoint = len(messages)
        try:
            yield from self._chat_inner(user_message, messages)
        except Exception:
            del messages[checkpoint:]
            raise

    def _chat_inner(self, user_message: str, messages: list[dict]) -> Generator[str, None, None]:
        active_tools = self._get_active_tools()
        system = self._build_system_prompt()

        messages.append({"role": "user", "content": user_message})

        for _ in range(_MAX_TURNS):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=system,
                tools=active_tools,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        yield block.text
                return

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result_text = self._execute_tool_block(block)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": [{"type": "text", "text": result_text}],
                        })
                messages.append({"role": "user", "content": tool_results})
                continue

            break

        yield "[Agent reached maximum tool iterations without a final answer]"

    def chat_stream(self, user_message: str, messages: list[dict]) -> Iterable[dict]:
        """Run one user turn with streaming output and visible tool activity."""
        checkpoint = len(messages)
        try:
            yield from self._chat_stream_inner(user_message, messages)
        except Exception:
            del messages[checkpoint:]
            raise

    def _chat_stream_inner(self, user_message: str, messages: list[dict]) -> Iterable[dict]:
        active_tools = self._get_active_tools()
        system = self._build_system_prompt()

        messages.append({"role": "user", "content": user_message})

        for _ in range(_MAX_TURNS):
            with self._client.messages.stream(
                model=self._model,
                max_tokens=2048,
                system=system,
                tools=active_tools,
                messages=messages,
            ) as stream:
                for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta.type == "text_delta"
                    ):
                        yield {"type": "text_delta", "text": event.delta.text}

                final_message = stream.get_final_message()

            messages.append({"role": "assistant", "content": final_message.content})

            if final_message.stop_reason == "end_turn":
                text_blocks = [
                    block.text
                    for block in final_message.content
                    if block.type == "text"
                ]
                yield {
                    "type": "done",
                    "text": "".join(text_blocks),
                    "stop_reason": final_message.stop_reason,
                }
                return

            if final_message.stop_reason == "tool_use":
                tool_results = []
                for block in final_message.content:
                    if block.type != "tool_use":
                        continue
                    yield {
                        "type": "tool_start",
                        "tool_name": block.name,
                        "tool_input": block.input,
                    }
                    result_text = self._execute_tool_block(block)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": [{"type": "text", "text": result_text}],
                    })
                    yield {
                        "type": "tool_result",
                        "tool_name": block.name,
                        "result": result_text,
                    }
                messages.append({"role": "user", "content": tool_results})
                continue

            break

        yield {
            "type": "error",
            "text": "[Agent reached maximum tool iterations without a final answer]",
        }

