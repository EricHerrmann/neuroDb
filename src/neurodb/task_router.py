"""TaskRouter — maps task_type to (ModelClient, model_id, max_tokens)."""
from __future__ import annotations

from neurodb.model_client import ModelClient
from neurodb.model_config import get_model_for_task


class TaskRouter:
    """Routes task types to the appropriate ModelClient and model configuration."""

    def __init__(self, providers: dict[str, ModelClient]) -> None:
        self._providers = providers

    def route(self, task_type: str) -> tuple[ModelClient, str, int]:
        """Return (ModelClient, model_id, max_tokens) for the given task type.

        Raises KeyError if task_type is unknown or if the required provider
        is not registered.
        """
        provider_name, model_id, max_tokens = get_model_for_task(task_type)
        if provider_name not in self._providers:
            raise KeyError(provider_name)
        return self._providers[provider_name], model_id, max_tokens
