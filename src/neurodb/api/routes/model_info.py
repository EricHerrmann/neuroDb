"""GET /api/model-info — returns active provider and model for each agent mode."""
from __future__ import annotations

from fastapi import APIRouter

from neurodb.config.model_config import get_route_config_for_task

router = APIRouter()

_AGENT_MODES = ("local_db", "external_db", "neuro_tutor", "neuro_research")


@router.get("/model-info")
def get_model_info() -> dict[str, dict[str, str]]:
    result = {}
    for mode in _AGENT_MODES:
        _, provider, model_id, _ = get_route_config_for_task(f"agent.loop.{mode}")
        result[mode] = {"provider": provider, "model": model_id}
    return result
