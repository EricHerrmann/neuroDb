"""Abstract base class for NeuroDb agents."""
from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable
from time import perf_counter

from neurodb.config.model_client import ContentBlock, ModelClient
from neurodb.model_telemetry import record_model_call

_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_TURNS = 10


class BaseAgent(ABC):
    """Shared tool-use loop for all NeuroDb agents (provider-neutral via ModelClient)."""

    def __init__(
        self,
        client=None,
        engine=None,
        vector_store=None,
        model: str = _DEFAULT_MODEL,
        prior_context: str = "",
        max_tool_iterations: int = _MAX_TURNS,
        save_partial_progress_on_budget: bool = False,
        max_tokens: int = 2048,
        telemetry_mode: str | None = None,
        telemetry_task_type: str | None = None,
        model_client: ModelClient | None = None,
        model_provider: str = "anthropic",
    ) -> None:
        self._client = client
        self._engine = engine
        self._vector_store = vector_store
        self._model = model
        self.prior_context = prior_context
        self._max_tool_iterations = max_tool_iterations
        self._save_partial_progress_on_budget = save_partial_progress_on_budget
        self._max_tokens = max_tokens
        self._telemetry_mode = telemetry_mode
        self._telemetry_task_type = (
            telemetry_task_type
            or f"agent.loop.{telemetry_mode or 'unknown'}"
        )
        self._model_provider = model_provider
        if model_client is not None:
            self._model_client = model_client
        elif client is not None:
            from neurodb.config.providers.anthropic_client import AnthropicModelClient
            self._model_client = AnthropicModelClient(client)
        else:
            raise ValueError("Either client or model_client must be provided")

    @abstractmethod
    def _get_active_tools(self) -> list[dict]:
        """Return tool definitions available to this agent."""

    @abstractmethod
    def _build_system_prompt(self) -> str:
        """Return the system prompt for the current agent state."""

    @abstractmethod
    def _execute_tool_block(self, block: ContentBlock) -> str:
        """Execute a tool call and return text for tool_result."""

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

        for iteration in range(self._max_tool_iterations):
            started = perf_counter()
            response = self._model_client.create_message(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                tools=active_tools,
                messages=messages,
            )
            elapsed_ms = int((perf_counter() - started) * 1000)
            self._record_model_call(response, iteration + 1, elapsed_ms)
            messages.append({"role": "assistant", "content": _blocks_to_dicts(response.content)})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        yield block.text
                return

            if response.stop_reason == "tool_use":
                progress_notes.extend(
                    block.text.strip()
                    for block in response.content
                    if block.type == "text" and block.text and block.text.strip()
                )
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result_text = self._execute_tool_block(block)
                        tool_trace.append({
                            "tool": block.tool_name,
                            "input": block.tool_input,
                            "result": result_text,
                        })
                        tool_results.append(
                            self._model_client.format_tool_result(block.tool_use_id, result_text)
                        )
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
            started = perf_counter()
            with self._model_client.stream_message(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                tools=active_tools,
                messages=messages,
            ) as stream:
                for delta in stream:
                    if delta.get("type") == "text_delta":
                        text_fragments.append(delta["text"])
                        yield delta

                response = stream.get_final_message()
            elapsed_ms = int((perf_counter() - started) * 1000)
            self._record_model_call(response, iteration + 1, elapsed_ms)

            messages.append({"role": "assistant", "content": _blocks_to_dicts(response.content)})

            if response.stop_reason == "end_turn":
                text_blocks = [
                    block.text
                    for block in response.content
                    if block.type == "text"
                ]
                yield {
                    "type": "done",
                    "text": "".join(t for t in text_blocks if t),
                    "stop_reason": response.stop_reason,
                }
                return

            if response.stop_reason == "tool_use":
                progress_text = "".join(text_fragments).strip()
                if progress_text:
                    progress_notes.append(progress_text)
                text_fragments.clear()
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    yield {
                        "type": "tool_start",
                        "tool_name": block.tool_name,
                        "tool_input": block.tool_input,
                        "iteration": iteration + 1,
                        "limit": self._max_tool_iterations,
                    }
                    result_text = self._execute_tool_block(block)
                    tool_trace.append({
                        "tool": block.tool_name,
                        "input": block.tool_input,
                        "result": result_text,
                    })
                    tool_results.append(
                        self._model_client.format_tool_result(block.tool_use_id, result_text)
                    )
                    yield {
                        "type": "tool_result",
                        "tool_name": block.tool_name,
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

            if response.stop_reason == "max_tokens":
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

    def _record_model_call(self, response, iteration: int, elapsed_ms: int) -> None:
        try:
            record_model_call(
                self._engine,
                task_type=self._telemetry_task_type,
                provider=self._model_provider,
                model=self._model,
                mode=self._telemetry_mode,
                response=response,
                iteration=iteration,
                elapsed_ms=elapsed_ms,
            )
        except Exception:
            return

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


def _blocks_to_dicts(blocks: list) -> list[dict]:
    """Convert ContentBlock list to Anthropic-format content dicts for message history."""
    result = []
    for block in blocks:
        if block.type == "text":
            result.append({"type": "text", "text": block.text or ""})
        elif block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.tool_use_id,
                "name": block.tool_name,
                "input": block.tool_input or {},
            })
    return result


def _preview(value: str, limit: int) -> str:
    collapsed = " ".join(str(value).split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3]}..."
