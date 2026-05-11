"""Provider-neutral ModelClient abstraction for NeuroDb agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ContextManager, Iterator, Protocol


@dataclass
class ContentBlock:
    """Normalized content block returned by any model provider."""
    type: str
    text: str | None = None
    tool_name: str | None = None
    tool_use_id: str | None = None
    tool_input: dict | None = None


@dataclass
class ModelResponse:
    """Normalized response from any model provider."""
    stop_reason: str
    content: list[ContentBlock] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None


class ModelStream(Protocol):
    """Protocol for normalized streaming responses."""

    def __iter__(self) -> Iterator[dict]: ...

    def get_final_message(self) -> ModelResponse: ...


class ModelClient(ABC):
    """Abstract base for provider-specific model adapters."""

    @abstractmethod
    def create_message(
        self,
        model: str,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int,
        tool_choice: str | None = None,
    ) -> ModelResponse:
        """Send a non-streaming message and return a normalized response.

        tool_choice: pass "required" to force the model to call one of the provided tools.
        """

    @abstractmethod
    def stream_message(
        self,
        model: str,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int,
    ) -> ContextManager[ModelStream]:
        """Return a context manager that yields a ModelStream."""

    @abstractmethod
    def format_tool(self, tool_definition: dict) -> dict:
        """Translate a tool definition dict to provider format."""

    @abstractmethod
    def format_tool_result(self, tool_use_id: str, content: str) -> dict:
        """Build a tool result dict in provider format."""
