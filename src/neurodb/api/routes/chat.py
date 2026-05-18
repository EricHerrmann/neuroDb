"""Chat SSE streaming route for the NeuroDb FastAPI backend."""
from __future__ import annotations

import json
from collections.abc import Generator
from unittest.mock import Mock

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import Engine

from neurodb.agents.db_agent import NeuroDbAgent
from neurodb.agents.research_agent import NeuroResearchAgent
from neurodb.agents.tutor_agent import NeuroTutorAgent
from neurodb.api.deps import VALID_AGENT_MODES, get_engine, get_research_stores
from neurodb.api.schemas.chat import ChatTurnRequest
from neurodb.config.provider_factory import build_provider_clients
from neurodb.config.task_router import TaskRouter

router = APIRouter()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _build_agent(
    agent_mode: str,
    engine,
    vector_store,
    knowledge_store,
    context_store,
    providers: dict,
    prior_context: str = "",
):
    router_obj = TaskRouter(providers)
    route = router_obj.route(f"agent.loop.{agent_mode}")
    if agent_mode == "neuro_research":
        return NeuroResearchAgent(
            model_client=route.model_client,
            model=route.model_id,
            max_tokens=route.max_tokens,
            engine=engine,
            vector_store=vector_store,
            knowledge_store=knowledge_store,
            context_store=context_store,
            prior_context=prior_context,
            model_provider=route.provider,
        )
    if agent_mode == "neuro_tutor":
        return NeuroTutorAgent(
            model_client=route.model_client,
            model=route.model_id,
            engine=engine,
            vector_store=vector_store,
            knowledge_store=knowledge_store,
            prior_context=prior_context,
            model_provider=route.provider,
        )
    return NeuroDbAgent(
        model_client=route.model_client,
        model=route.model_id,
        max_tokens=route.max_tokens,
        engine=engine,
        vector_store=vector_store,
        mode=agent_mode,
        prior_context=prior_context,
        model_provider=route.provider,
    )


def _get_prior_context(request: Request, engine) -> str:
    manager = getattr(request.app.state, "session_manager", None)
    if manager is None:
        return ""
    context, _topic = manager.get_most_recent_session_info(engine)
    return context


def _stream_chat(agent, message: str, history: list[dict]) -> Generator[str, None, None]:
    """Drive agent.chat() and emit SSE events."""
    chat_stream = getattr(agent, "chat_stream", None)
    if callable(chat_stream) and not isinstance(chat_stream, Mock):
        try:
            for event in chat_stream(message, history):
                yield _sse(event)
            return
        except AttributeError:
            pass

    full_text_parts: list[str] = []
    try:
        for chunk in agent.chat(message, history):
            full_text_parts.append(chunk)
            yield _sse({"type": "text_delta", "text": chunk})
        full_text = "".join(full_text_parts)
        yield _sse({"type": "done", "text": full_text, "stop_reason": "end_turn"})
    except Exception as exc:
        yield _sse({"type": "error", "text": str(exc)})


@router.post("/chat/turn")
def chat_turn(
    body: ChatTurnRequest,
    request: Request,
    engine: Engine = Depends(get_engine),
):
    if body.agent_mode not in VALID_AGENT_MODES:
        return JSONResponse(
            status_code=400,
            content={
                "detail": (
                    f"Unknown agent_mode '{body.agent_mode}'. "
                    f"Valid modes: {sorted(VALID_AGENT_MODES)}"
                )
            },
        )

    providers = build_provider_clients()
    if not providers:
        return JSONResponse(
            status_code=503,
            content={"detail": "No AI provider API keys configured."},
        )

    stores = get_research_stores(request)
    history = [{"role": m.role, "content": m.content} for m in body.history]
    prior_context = _get_prior_context(request, engine)
    agent = _build_agent(
        body.agent_mode,
        engine,
        stores["vector_store"],
        stores["knowledge_store"],
        stores["context_store"],
        providers,
        prior_context,
    )

    return StreamingResponse(
        _stream_chat(agent, body.message, history),
        media_type="text/event-stream",
    )
