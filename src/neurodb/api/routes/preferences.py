"""GET /api/preferences and PUT /api/preferences/agent-mode routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from neurodb.agents.context_orchestrator import (
    DEFAULT_CONTEXT_MODE,
    normalize_context_mode,
)
from neurodb.api.deps import VALID_AGENT_MODES, get_engine
from neurodb.api.schemas.preferences import (
    AgentModeResponse,
    AgentModeUpdate,
    ContextModeResponse,
    ContextModeUpdate,
    PreferencesResponse,
)
from neurodb.prefs import load_prefs
from neurodb.research_tools import load_app_preference, save_app_preference

router = APIRouter()


@router.get("/preferences", response_model=PreferencesResponse)
def get_preferences(engine: Engine = Depends(get_engine)) -> PreferencesResponse:
    agent_mode = load_app_preference(engine, "agent_mode", "local_db")
    context_mode = load_app_preference(engine, "context_mode", DEFAULT_CONTEXT_MODE)
    prefs = load_prefs()
    return PreferencesResponse(
        agent_mode=agent_mode,
        context_mode=normalize_context_mode(context_mode),
        relevance_threshold=prefs["relevance_threshold"],
    )


@router.put("/preferences/agent-mode", response_model=AgentModeResponse)
def put_agent_mode(
    body: AgentModeUpdate,
    engine: Engine = Depends(get_engine),
) -> AgentModeResponse:
    if body.mode not in VALID_AGENT_MODES:
        raise HTTPException(status_code=400, detail=f"Unknown agent mode: {body.mode!r}")
    save_app_preference(engine, "agent_mode", body.mode)
    return AgentModeResponse(agent_mode=body.mode)


@router.put("/preferences/context-mode", response_model=ContextModeResponse)
def put_context_mode(
    body: ContextModeUpdate,
    engine: Engine = Depends(get_engine),
) -> ContextModeResponse:
    try:
        mode = normalize_context_mode(body.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_app_preference(engine, "context_mode", mode)
    return ContextModeResponse(context_mode=mode)
