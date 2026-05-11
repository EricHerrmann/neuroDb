"""TaskRouter — maps task_type to (ModelClient, model_id, max_tokens)."""
from __future__ import annotations

from dataclasses import dataclass

from neurodb.config.model_client import ModelClient
from neurodb.config.model_config import get_route_config_for_task


@dataclass(frozen=True)
class ModelRoute:
    """Resolved model route for one task type."""

    task_type: str
    tier: str
    provider: str
    model_client: ModelClient
    model_id: str
    max_tokens: int


class TaskRouter:
    """Routes task types to the appropriate ModelClient and model configuration."""

    def __init__(self, providers: dict[str, ModelClient]) -> None:
        self._providers = providers

    def route(self, task_type: str) -> ModelRoute:
        """Return the provider/client/model route for the given task type.

        Raises KeyError if task_type is unknown or if the required provider
        is not registered.
        """
        tier, provider_name, model_id, max_tokens = get_route_config_for_task(task_type)
        if provider_name not in self._providers:
            raise KeyError(provider_name)
        return ModelRoute(
            task_type=task_type,
            tier=tier,
            provider=provider_name,
            model_client=self._providers[provider_name],
            model_id=model_id,
            max_tokens=max_tokens,
        )
