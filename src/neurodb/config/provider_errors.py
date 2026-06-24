"""Shared retry/fallback classification for model provider errors."""
from __future__ import annotations

RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504, 529}
RETRY_DELAYS_SECONDS = (0.25, 0.75)


def is_retryable_provider_error(exc: Exception) -> bool:
    """Return True when a provider failure should be retried or runtime-fallbacked."""
    status_code = _get_value(exc, "status_code")
    if status_code in RETRYABLE_STATUS_CODES:
        return True

    error_type = _extract_error_type(exc)
    if error_type in {"overloaded_error", "rate_limit_error"}:
        return True

    message = str(exc)
    if any(f"Error code: {code}" in message for code in RETRYABLE_STATUS_CODES):
        return True
    return "overloaded_error" in message or "Overloaded" in message


def _extract_error_type(exc: Exception) -> str | None:
    direct = _get_value(exc, "type")
    if isinstance(direct, str):
        return direct

    body = _get_value(exc, "body")
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("type"), str):
            return error["type"]
        if isinstance(body.get("type"), str):
            return body["type"]

    response = _get_value(exc, "response")
    if response is not None:
        json_fn = _get_value(response, "json")
        if callable(json_fn):
            try:
                data = json_fn()
            except Exception:
                data = None
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, dict) and isinstance(error.get("type"), str):
                    return error["type"]
    return None


def _get_value(obj, name: str):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
