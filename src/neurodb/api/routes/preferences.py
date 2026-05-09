"""GET /api/preferences and PUT /api/preferences/agent-mode routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.preferences import AgentModeResponse, AgentModeUpdate, PreferencesResponse
from neurodb.prefs import load_prefs
from neurodb.research_tools import load_app_preference, save_app_preference

router = APIRouter()

_VALID_MODES = {"local_db", "external_db", "neuro_tutor", "neuro_research"}


@router.get("/preferences", response_model=PreferencesResponse)
def get_preferences(engine: Engine = Depends(get_engine)) -> PreferencesResponse:
    agent_mode = load_app_preference(engine, "agent_mode", "local_db")
    prefs = load_prefs()
    return PreferencesResponse(
        agent_mode=agent_mode,
        relevance_threshold=prefs["relevance_threshold"],
    )


@router.put("/preferences/agent-mode", response_model=AgentModeResponse)
def put_agent_mode(
    body: AgentModeUpdate,
    engine: Engine = Depends(get_engine),
) -> AgentModeResponse:
    if body.mode not in _VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Unknown agent mode: {body.mode!r}")
    save_app_preference(engine, "agent_mode", body.mode)
    return AgentModeResponse(agent_mode=body.mode)
