"""Config Control epoch — local model-call telemetry helpers."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from neurodb.db import get_session
from neurodb.schema import ModelCallLog, SystemWarning

_PRICE_PER_MILLION_TOKENS_USD: dict[str, tuple[float, float]] = {}


def build_model_call_log(
    *,
    task_type: str,
    provider: str,
    model: str,
    mode: str | None = None,
    response=None,
    iteration: int | None = None,
    elapsed_ms: int | None = None,
) -> ModelCallLog:
    """Build a ModelCallLog row from a provider response."""
    input_tokens, output_tokens = _extract_usage(response)
    tool_names = _extract_tool_names(response)
    return ModelCallLog(
        recorded_at=datetime.now(UTC).isoformat(),
        task_type=task_type,
        provider=provider,
        model=model,
        mode=mode,
        tool_name=tool_names[0] if tool_names else None,
        tool_names_json=json.dumps(tool_names) if tool_names else None,
        iteration=iteration,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        stop_reason=_get_value(response, "stop_reason"),
        elapsed_ms=elapsed_ms,
        estimated_cost_usd=_estimate_cost_usd(model, input_tokens, output_tokens),
    )


def record_model_call(engine, **kwargs) -> None:
    """Write one telemetry row using a short independent session."""
    if engine is None:
        return
    try:
        row = build_model_call_log(**kwargs)
        with get_session(engine) as session:
            session.add(row)
    except Exception:
        return


def add_model_call_log(session, **kwargs) -> None:
    """Attach one telemetry row to an existing transaction."""
    if session is None:
        return
    try:
        session.add(build_model_call_log(**kwargs))
    except Exception:
        return


def build_system_warning(
    *,
    warning_type: str,
    severity: str,
    task_type: str,
    message: str,
    requested_provider: str | None = None,
    selected_provider: str | None = None,
) -> SystemWarning:
    """Build a SystemWarning row for provider routing and runtime anomalies."""
    return SystemWarning(
        recorded_at=datetime.now(UTC).isoformat(),
        warning_type=warning_type,
        severity=severity,
        task_type=task_type,
        requested_provider=requested_provider,
        selected_provider=selected_provider,
        message=message,
    )


def record_system_warning(engine, **kwargs) -> None:
    """Write one system warning row; never let warning persistence break runtime flow."""
    if engine is None:
        return
    try:
        row = build_system_warning(**kwargs)
        with get_session(engine) as session:
            session.add(row)
    except Exception:
        return


def _extract_usage(response) -> tuple[int | None, int | None]:
    # Check for direct token fields on ModelResponse
    input_direct = _get_value(response, "input_tokens")
    output_direct = _get_value(response, "output_tokens")
    if input_direct is not None or output_direct is not None:
        return input_direct, output_direct
    # Fall back to nested usage object from Anthropic SDK response
    usage = _get_value(response, "usage")
    if usage is None:
        return None, None
    return _get_value(usage, "input_tokens"), _get_value(usage, "output_tokens")


def _extract_tool_names(response) -> list[str]:
    content = _get_value(response, "content") or []
    names: list[str] = []
    for block in content:
        if _get_value(block, "type") != "tool_use":
            continue
        # Support both SDK blocks (.name) and normalized ContentBlock (.tool_name)
        name = _get_value(block, "name") or _get_value(block, "tool_name")
        if name:
            names.append(str(name))
    return names


def _estimate_cost_usd(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    pricing = _PRICE_PER_MILLION_TOKENS_USD.get(model)
    if pricing is None or input_tokens is None or output_tokens is None:
        return None
    input_price, output_price = pricing
    return (input_tokens / 1_000_000 * input_price) + (
        output_tokens / 1_000_000 * output_price
    )


def _get_value(obj, name: str):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
