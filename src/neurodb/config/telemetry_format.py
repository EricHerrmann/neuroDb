"""Formatting helpers shared by telemetry surfaces."""
from __future__ import annotations

from datetime import datetime


def format_recorded_at(value: str | None) -> str:
    """Format an ISO timestamp as HH:MM:SS DD/MM/YY for operator-facing output."""
    if not value:
        return ""
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    return dt.strftime("%H:%M:%S %d/%m/%y")
