"""Config-driven model routing table — loads neurodb_models.toml."""
from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

_CONFIG_PATH = Path(__file__).parent.parent.parent / "neurodb_models.toml"
_cache: dict | None = None


def load_model_config() -> dict:
    """Read and return the model routing TOML config (cached after first load)."""
    global _cache
    if _cache is None:
        with open(_CONFIG_PATH, "rb") as fh:
            _cache = tomllib.load(fh)
    return _cache


def get_model_for_task(task_type: str) -> tuple[str, str, int]:
    """Return (provider, model_id, max_tokens) for the given task type.

    Raises KeyError if task_type is not defined in the config.
    """
    config = load_model_config()
    tasks = config.get("tasks", {})
    if task_type not in tasks:
        raise KeyError(task_type)

    task_cfg = tasks[task_type]
    tier_name = task_cfg["tier"]
    max_tokens = task_cfg["max_tokens"]

    tier_cfg = config["tiers"][tier_name]
    provider = tier_cfg["default_provider"]
    model_id = tier_cfg["providers"][provider]["model"]

    return provider, model_id, max_tokens
