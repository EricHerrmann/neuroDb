"""TaskRouter — maps task_type to (ModelClient, model_id, max_tokens)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine

from neurodb.config.model_client import ModelClient
from neurodb.config.model_config import (
    get_provider_fallback_order,
    get_task_config,
    get_tier_provider_config,
)
from neurodb.model_telemetry import record_system_warning


@dataclass(frozen=True)
class ModelRoute:
    """Resolved model route for one task type."""

    task_type: str
    tier: str
    provider: str
    model_client: ModelClient
    model_id: str
    max_tokens: int


class RoutingError(Exception):
    """Raised when no provider in the fallback chain can serve a task type."""


class TaskRouter:
    """Routes task types to the appropriate ModelClient and model configuration."""

    def __init__(self, providers: dict[str, ModelClient]) -> None:
        self._providers = providers

    def route(self, task_type: str, *, engine: Engine | None = None) -> ModelRoute:
        """Return the provider/client/model route for the given task type.

        Raises KeyError if task_type is unknown.
        Raises RoutingError if no configured fallback provider can serve the task.
        """
        tier, max_tokens = get_task_config(task_type)
        candidates = get_provider_fallback_order(tier)
        primary = candidates[0]
        uses_tools, is_agent_loop = _infer_task_capabilities(task_type)
        skipped: list[tuple[str, str]] = []

        for provider_name in candidates:
            provider_cfg = _provider_cfg_or_none(tier, provider_name)
            reason = _rejection_reason(
                provider_name=provider_name,
                provider_cfg=provider_cfg,
                registered_provider=provider_name in self._providers,
                uses_tools=uses_tools,
                is_agent_loop=is_agent_loop,
            )
            if reason is not None:
                skipped.append((provider_name, reason))
                _record_routing_warning(
                    engine,
                    warning_type=_warning_type_for_reason(reason),
                    severity="warning",
                    task_type=task_type,
                    requested_provider=provider_name,
                    selected_provider=None,
                    message=_skip_message(provider_name, reason),
                )
                continue

            if provider_cfg is None:
                continue
            if provider_name != primary:
                summary = _summarize_skips(skipped)
                _record_routing_warning(
                    engine,
                    warning_type="routing_fallback",
                    severity="info",
                    task_type=task_type,
                    requested_provider=primary,
                    selected_provider=provider_name,
                    message=f"selected fallback: {provider_name} ({summary})",
                )
            model_id = provider_cfg["model"]
            return ModelRoute(
                task_type=task_type,
                tier=tier,
                provider=provider_name,
                model_client=self._providers[provider_name],
                model_id=model_id,
                max_tokens=max_tokens,
            )

        message = f"no viable provider found: {_summarize_skips(skipped)}"
        _record_routing_warning(
            engine,
            warning_type="routing_failed",
            severity="error",
            task_type=task_type,
            requested_provider=None,
            selected_provider=None,
            message=message,
        )
        raise RoutingError(message)


def _provider_cfg_or_none(tier: str, provider_name: str) -> dict | None:
    try:
        return get_tier_provider_config(tier, provider_name)
    except KeyError:
        return None


def _infer_task_capabilities(task_type: str) -> tuple[bool | None, bool | None]:
    if task_type.startswith("summary."):
        return False, False
    if task_type.startswith("agent.loop."):
        return True, True
    if task_type.startswith("research."):
        return True, False
    return None, None


def _rejection_reason(
    *,
    provider_name: str,
    provider_cfg: dict | None,
    registered_provider: bool,
    uses_tools: bool | None,
    is_agent_loop: bool | None,
) -> str | None:
    if provider_cfg is None:
        return "provider not configured for tier"
    if not registered_provider:
        return "missing API key"
    if provider_cfg.get("eval_status") == "degraded":
        return "degraded"
    if provider_cfg.get("requires_tools") is True and uses_tools is False:
        return "capability_mismatch: requires tools"
    if provider_cfg.get("tool_loop_reliable") is False and is_agent_loop is True:
        return "capability_mismatch: tool loop unreliable"
    return None


def _warning_type_for_reason(reason: str) -> str:
    if reason == "missing API key" or reason == "provider not configured for tier":
        return "provider_missing"
    if reason == "degraded":
        return "provider_degraded"
    return "capability_mismatch"


def _skip_message(provider_name: str, reason: str) -> str:
    if reason == "missing API key":
        return f"{provider_name} not registered (missing API key)"
    return f"{provider_name} skipped: {reason}"


def _summarize_skips(skipped: list[tuple[str, str]]) -> str:
    if not skipped:
        return "no providers skipped"
    return ", ".join(f"{provider} ({reason})" for provider, reason in skipped)


def _record_routing_warning(
    engine: Engine | None,
    *,
    warning_type: str,
    severity: str,
    task_type: str,
    requested_provider: str | None,
    selected_provider: str | None,
    message: str,
) -> None:
    record_system_warning(
        engine,
        warning_type=warning_type,
        severity=severity,
        task_type=task_type,
        requested_provider=requested_provider,
        selected_provider=selected_provider,
        message=message,
    )
