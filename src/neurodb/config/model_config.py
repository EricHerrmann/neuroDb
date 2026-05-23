"""Config-driven model routing table — loads neurodb_models.toml."""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "neurodb_models.toml"
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
    provider = _provider_for_tier(tier_name, tier_cfg)
    model_id = tier_cfg["providers"][provider]["model"]

    return provider, model_id, max_tokens


def get_route_config_for_task(task_type: str) -> tuple[str, str, str, int]:
    """Return (tier, provider, model_id, max_tokens) for the given task type."""
    tier_name, max_tokens = get_task_config(task_type)
    provider = get_primary_provider_for_tier(tier_name)
    model_id = get_tier_provider_config(tier_name, provider)["model"]

    return tier_name, provider, model_id, max_tokens


def get_task_config(task_type: str) -> tuple[str, int]:
    """Return (tier, max_tokens) for a configured task type."""
    config = load_model_config()
    tasks = config.get("tasks", {})
    if task_type not in tasks:
        raise KeyError(task_type)
    task_cfg = tasks[task_type]
    return task_cfg["tier"], task_cfg["max_tokens"]


def get_model_for_tier(tier_name: str) -> tuple[str, str]:
    """Return (provider, model_id) for an active capability tier."""
    provider = get_primary_provider_for_tier(tier_name)
    model_id = get_tier_provider_config(tier_name, provider)["model"]
    return provider, model_id


def get_primary_provider_for_tier(tier_name: str) -> str:
    """Return the primary provider configured for a tier."""
    config = load_model_config()
    tier_cfg = config["tiers"][tier_name]
    return _provider_for_tier(tier_name, tier_cfg)


def get_tier_provider_config(tier_name: str, provider: str) -> dict:
    """Return the provider config block for a tier/provider pair."""
    config = load_model_config()
    tier_cfg = config["tiers"][tier_name]
    providers = tier_cfg.get("providers", {})
    if provider not in providers:
        raise KeyError(f"{provider} provider is not configured for {tier_name} tier")
    return providers[provider]


def get_provider_fallback_order(tier_name: str) -> list[str]:
    """Return provider candidates in primary-plus-fallback order with duplicates removed."""
    config = load_model_config()
    primary = get_primary_provider_for_tier(tier_name)
    fallback = config.get("routing", {}).get(f"{tier_name}_fallback", [])
    ordered: list[str] = []
    for provider in [primary, *fallback]:
        if provider not in ordered:
            ordered.append(provider)
    return ordered


class ContextBudget(TypedDict):
    papers: int
    notes: int
    claims: int
    datasets: int


def get_context_budget(mode: str) -> "ContextBudget | None":
    """Return per-category item limits for the given context mode, or None if unconfigured."""
    config = load_model_config()
    mode_cfg = config.get("context_budgets", {}).get(mode)
    if mode_cfg is None:
        return None
    return {
        "papers": int(mode_cfg["papers"]),
        "notes": int(mode_cfg["notes"]),
        "claims": int(mode_cfg["claims"]),
        "datasets": int(mode_cfg["datasets"]),
    }


def _provider_for_tier(tier_name: str, tier_cfg: dict) -> str:
    config = load_model_config()
    provider = config["routing"][tier_name]
    if provider not in tier_cfg.get("providers", {}):
        raise KeyError(f"{provider} provider is not configured for {tier_name} tier")
    return provider
