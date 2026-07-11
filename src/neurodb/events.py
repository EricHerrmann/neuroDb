"""Minimal synchronous in-process domain-event emitter (workstream 3).

Single-process by design — no bus, no queue. Handlers run in the emitting
request/thread. A handler error is logged and recorded in the emit outcome,
never raised to the caller and never allowed to stop later handlers.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

FULL_TEXT_ACQUIRED = "full_text_acquired"

_registry: dict[str, dict[str, Callable[..., object]]] = {}


def subscribe(name: str, handler: Callable[..., object], *,
              key: str | None = None) -> None:
    """Register handler for event `name`. Same key replaces (idempotent startup)."""
    handlers = _registry.setdefault(name, {})
    handlers[key or f"{handler.__module__}.{handler.__qualname__}"] = handler


def emit(name: str, **payload) -> list[dict]:
    """Dispatch synchronously to all subscribers; return per-handler outcomes."""
    outcomes: list[dict] = []
    for key, handler in list(_registry.get(name, {}).items()):
        try:
            handler(**payload)
            outcomes.append({"handler": key, "status": "ok", "error": None})
        except Exception as exc:
            logger.exception("event handler %s failed for event %s", key, name)
            outcomes.append({"handler": key, "status": "error", "error": str(exc)})
    return outcomes


def reset() -> None:
    """Test hook: clear all subscriptions."""
    _registry.clear()
