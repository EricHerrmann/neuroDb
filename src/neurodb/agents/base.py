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
        max_tool_iterations: int = _MAX_TURNS,
        save_partial_progress_on_budget: bool = False,
        max_tokens: int = 2048,
    ) -> None:
        self._client = client
        self._engine = engine
        self._vector_store = vector_store
        self._model = model
        self.prior_context = prior_context
        self._max_tool_iterations = max_tool_iterations
        self._save_partial_progress_on_budget = save_partial_progress_on_budget
        self._max_tokens = max_tokens

    @abstractmethod
    def _get_active_tools(self) -> list[dict]:
        """Return tool definitions available to this agent."""

    @abstractmethod
    def _build_system_prompt(self) -> str:
        """Return the system prompt for the current agent state."""

    @abstractmethod
    def _execute_tool_block(self, block) -> str:
        """Execute a Claude tool-use block and return text for tool_result."""

    def _build_terminal_tool_response(self, tool_trace: list[dict]) -> str | None:
        """Return a final assistant response when a tool result completes the turn."""
        return None

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

        checkpoint = len(messages)
        messages.append({"role": "user", "content": user_message})
        progress_notes: list[str] = []
        tool_trace: list[dict] = []

        for _ in range(self._max_tool_iterations):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
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
                progress_notes.extend(
                    block.text.strip()
                    for block in response.content
                    if block.type == "text" and block.text.strip()
                )
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result_text = self._execute_tool_block(block)
                        tool_trace.append({
                            "tool": block.name,
                            "input": block.input,
                            "result": result_text,
                        })
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": [{"type": "text", "text": result_text}],
                        })
                messages.append({"role": "user", "content": tool_results})
                terminal_response = self._build_terminal_tool_response(tool_trace)
                if terminal_response:
                    messages.append({
                        "role": "assistant",
                        "content": [{"type": "text", "text": terminal_response}],
                    })
                    yield terminal_response
                    return
                continue

            if response.stop_reason == "max_tokens":
                del messages[checkpoint:]
                yield (
                    f"[Response truncated: the model hit the token limit "
                    f"({self._max_tokens} tokens) before completing the tool call. "
                    "Retry with a narrower request.]"
                )
                return

            break

        yield self._handle_iteration_budget_exhausted(
            messages,
            checkpoint,
            user_message,
            progress_notes,
            tool_trace,
        )

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

        checkpoint = len(messages)
        messages.append({"role": "user", "content": user_message})
        text_fragments: list[str] = []
        progress_notes: list[str] = []
        tool_trace: list[dict] = []

        for iteration in range(self._max_tool_iterations):
            with self._client.messages.stream(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                tools=active_tools,
                messages=messages,
            ) as stream:
                for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta.type == "text_delta"
                    ):
                        text_fragments.append(event.delta.text)
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
                progress_text = "".join(text_fragments).strip()
                if progress_text:
                    progress_notes.append(progress_text)
                text_fragments.clear()
                tool_results = []
                for block in final_message.content:
                    if block.type != "tool_use":
                        continue
                    yield {
                        "type": "tool_start",
                        "tool_name": block.name,
                        "tool_input": block.input,
                        "iteration": iteration + 1,
                        "limit": self._max_tool_iterations,
                    }
                    result_text = self._execute_tool_block(block)
                    tool_trace.append({
                        "tool": block.name,
                        "input": block.input,
                        "result": result_text,
                    })
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
                terminal_response = self._build_terminal_tool_response(tool_trace)
                if terminal_response:
                    messages.append({
                        "role": "assistant",
                        "content": [{"type": "text", "text": terminal_response}],
                    })
                    yield {
                        "type": "done",
                        "text": terminal_response,
                        "stop_reason": "terminal_tool_result",
                    }
                    return
                continue

            if final_message.stop_reason == "max_tokens":
                del messages[checkpoint:]
                yield {
                    "type": "error",
                    "text": (
                        f"[Response truncated: the model hit the token limit "
                        f"({self._max_tokens} tokens) before completing the tool call. "
                        "Retry with a narrower request.]"
                    ),
                }
                return

            break

        message = self._handle_iteration_budget_exhausted(
            messages,
            checkpoint,
            user_message,
            progress_notes,
            tool_trace,
        )
        yield {
            "type": "error",
            "text": message,
        }

    def _handle_iteration_budget_exhausted(
        self,
        messages: list[dict],
        checkpoint: int,
        user_message: str,
        progress_notes: list[str],
        tool_trace: list[dict],
    ) -> str:
        del messages[checkpoint:]
        base_message = (
            "[Agent reached maximum tool iterations "
            f"({self._max_tool_iterations}) without a final answer. "
        )
        if not self._save_partial_progress_on_budget:
            return (
                f"{base_message}The partial turn was not saved to API history; "
                "retry with a narrower request or ask the agent to draft from currently "
                "gathered evidence.]"
            )

        partial = self._build_partial_progress_note(user_message, progress_notes, tool_trace)
        messages.append({"role": "user", "content": user_message})
        messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": partial}],
        })
        return (
            f"{base_message}Partial research progress was saved to API history. "
            "You can ask me to continue, narrow the question, or draft from the saved "
            "evidence gathered so far.]"
        )

    def _build_partial_progress_note(
        self,
        user_message: str,
        progress_notes: list[str],
        tool_trace: list[dict],
    ) -> str:
        lines = [
            "Partial research progress saved before the tool-iteration budget was reached.",
            f"Original request: {user_message}",
        ]
        if progress_notes:
            lines.append("Intermediate notes:")
            for note in progress_notes[-4:]:
                lines.append(f"- {_preview(note, 300)}")
        if tool_trace:
            lines.append("Tool evidence gathered:")
            for idx, item in enumerate(tool_trace[-12:], start=1):
                input_preview = _preview(str(item["input"]), 180)
                result_preview = _preview(item["result"], 500)
                lines.append(
                    f"{idx}. {item['tool']} input={input_preview} result={result_preview}"
                )
        lines.append(
            "Next useful actions: continue from this saved evidence, narrow the request, "
            "or draft a hypothesis using only the evidence gathered so far."
        )
        return "\n".join(lines)


def _preview(value: str, limit: int) -> str:
    collapsed = " ".join(str(value).split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3]}..."
