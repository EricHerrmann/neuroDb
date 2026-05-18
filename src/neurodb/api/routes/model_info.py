"""GET /api/model-info — returns active provider and model routing."""
from __future__ import annotations

from fastapi import APIRouter

from neurodb.config.model_config import get_model_for_tier, get_route_config_for_task

router = APIRouter()

_AGENT_MODES = ("local_db", "external_db", "neuro_tutor", "neuro_research")
_DISPLAY_TIERS = {
    "low": "economy",
    "mid": "standard",
    "high": "premium",
}


@router.get("/model-info")
def get_model_info() -> dict[str, dict[str, dict[str, str]]]:
    agent_modes = {}
    for mode in _AGENT_MODES:
        tier, provider, model_id, _ = get_route_config_for_task(f"agent.loop.{mode}")
        agent_modes[mode] = {"tier": tier, "provider": provider, "model": model_id}

    tiers = {}
    for display_name, tier_name in _DISPLAY_TIERS.items():
        provider, model_id = get_model_for_tier(tier_name)
        tiers[display_name] = {
            "tier": tier_name,
            "provider": provider,
            "model": model_id,
        }

    return {"agent_modes": agent_modes, "tiers": tiers}
