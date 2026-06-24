"""Chat SSE streaming route for the NeuroDb FastAPI backend."""
from __future__ import annotations

import json
from collections.abc import Callable, Generator
from dataclasses import dataclass
from unittest.mock import Mock

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import Engine

from neurodb.agents.context_orchestrator import (
    DEFAULT_CONTEXT_MODE,
    build_context_bundle,
    normalize_context_mode,
)
from neurodb.agents.db_agent import NeuroDbAgent
from neurodb.agents.research_agent import NeuroResearchAgent
from neurodb.agents.tutor_agent import NeuroTutorAgent
from neurodb.api.deps import VALID_AGENT_MODES, get_engine, get_research_stores
from neurodb.api.schemas.chat import ChatTurnRequest
from neurodb.config.provider_errors import is_retryable_provider_error
from neurodb.config.provider_factory import build_provider_clients
from neurodb.config.task_router import ModelRoute, RoutingError, TaskRouter
from neurodb.research_tools import load_app_preference

router = APIRouter()


@dataclass(frozen=True)
class AgentAttempt:
    route: ModelRoute
    agent: object


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
    context_mode: str = DEFAULT_CONTEXT_MODE,
    context_bundle: dict | None = None,
    chunk_store=None,
    excluded_providers: set[str] | None = None,
):
    router_obj = TaskRouter(providers)
    route = router_obj.route_excluding(
        f"agent.loop.{agent_mode}",
        engine=engine,
        excluded_providers=excluded_providers,
    )
    return _build_agent_from_route(
        agent_mode,
        route,
        engine,
        vector_store,
        knowledge_store,
        context_store,
        prior_context,
        context_mode,
        context_bundle,
        chunk_store=chunk_store,
    )


def _build_agent_attempt(
    agent_mode: str,
    engine,
    vector_store,
    knowledge_store,
    context_store,
    providers: dict,
    prior_context: str = "",
    context_mode: str = DEFAULT_CONTEXT_MODE,
    context_bundle: dict | None = None,
    chunk_store=None,
    excluded_providers: set[str] | None = None,
) -> AgentAttempt:
    route = TaskRouter(providers).route_excluding(
        f"agent.loop.{agent_mode}",
        engine=engine,
        excluded_providers=excluded_providers,
    )
    agent = _build_agent_from_route(
        agent_mode,
        route,
        engine,
        vector_store,
        knowledge_store,
        context_store,
        prior_context,
        context_mode,
        context_bundle,
        chunk_store=chunk_store,
    )
    return AgentAttempt(route=route, agent=agent)


def _build_agent_from_route(
    agent_mode: str,
    route: ModelRoute,
    engine,
    vector_store,
    knowledge_store,
    context_store,
    prior_context: str = "",
    context_mode: str = DEFAULT_CONTEXT_MODE,
    context_bundle: dict | None = None,
    chunk_store=None,
):
    if agent_mode == "neuro_research":
        return NeuroResearchAgent(
            model_client=route.model_client,
            model=route.model_id,
            max_tokens=route.max_tokens,
            engine=engine,
            vector_store=vector_store,
            knowledge_store=knowledge_store,
            chunk_store=chunk_store,
            context_store=context_store,
            prior_context=prior_context,
            model_provider=route.provider,
            context_mode=context_mode,
            context_bundle=context_bundle,
        )
    if agent_mode == "neuro_tutor":
        return NeuroTutorAgent(
            model_client=route.model_client,
            model=route.model_id,
            engine=engine,
            vector_store=vector_store,
            knowledge_store=knowledge_store,
            chunk_store=chunk_store,
            prior_context=prior_context,
            model_provider=route.provider,
            context_mode=context_mode,
            context_bundle=context_bundle,
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


def _active_focus_from_body(body: ChatTurnRequest) -> dict | None:
    if body.active_focus_type is None and body.active_focus_id is None:
        return None
    if body.active_focus_type not in {"topic", "research_question"}:
        raise ValueError("active_focus_type must be 'topic' or 'research_question'")
    if body.active_focus_id is None:
        raise ValueError("active_focus_id is required when active_focus_type is set")
    return {"focus_type": body.active_focus_type, "focus_id": body.active_focus_id}


def _stream_chat(
    attempt: AgentAttempt,
    message: str,
    history: list[dict],
    fallback_factory: Callable[[set[str]], AgentAttempt] | None = None,
) -> Generator[str, None, None]:
    """Drive agent.chat() and emit SSE events."""
    excluded_providers: set[str] = set()
    current = attempt
    context_summary_sent = False

    while True:
        chat_stream = getattr(current.agent, "chat_stream", None)
        content_emitted = False
        if callable(chat_stream) and not isinstance(chat_stream, Mock):
            try:
                for event in chat_stream(message, history):
                    event_type = event.get("type")
                    if event_type == "context_summary":
                        if context_summary_sent:
                            continue
                        context_summary_sent = True
                    elif event_type in {"text_delta", "tool_start", "tool_result", "done"}:
                        content_emitted = True
                    yield _sse(event)
                return
            except AttributeError:
                pass
            except Exception as exc:
                fallback = _next_runtime_fallback(
                    exc,
                    current,
                    excluded_providers,
                    content_emitted,
                    fallback_factory,
                )
                if fallback is None:
                    yield _sse({"type": "error", "text": _provider_error_text(exc)})
                    return
                yield _sse(
                    _provider_fallback_event(
                        current.route.provider,
                        fallback.route.provider,
                        exc,
                    )
                )
                current = fallback
                continue

        full_text_parts: list[str] = []
        try:
            for chunk in current.agent.chat(message, history):
                content_emitted = True
                full_text_parts.append(chunk)
                yield _sse({"type": "text_delta", "text": chunk})
            full_text = "".join(full_text_parts)
            yield _sse({"type": "done", "text": full_text, "stop_reason": "end_turn"})
            return
        except Exception as exc:
            fallback = _next_runtime_fallback(
                exc,
                current,
                excluded_providers,
                content_emitted,
                fallback_factory,
            )
            if fallback is None:
                yield _sse({"type": "error", "text": _provider_error_text(exc)})
                return
            yield _sse(
                _provider_fallback_event(
                    current.route.provider,
                    fallback.route.provider,
                    exc,
                )
            )
            current = fallback


def _next_runtime_fallback(
    exc: Exception,
    current: AgentAttempt,
    excluded_providers: set[str],
    content_emitted: bool,
    fallback_factory: Callable[[set[str]], AgentAttempt] | None,
) -> AgentAttempt | None:
    if content_emitted or fallback_factory is None or not is_retryable_provider_error(exc):
        return None
    excluded_providers.add(current.route.provider)
    try:
        return fallback_factory(excluded_providers)
    except RoutingError:
        return None


def _provider_fallback_event(
    failed_provider: str,
    fallback_provider: str,
    exc: Exception,
) -> dict:
    reason = _provider_error_text(exc)
    return {
        "type": "provider_fallback",
        "failed_provider": failed_provider,
        "fallback_provider": fallback_provider,
        "text": (
            f"{failed_provider} failed after retries; using "
            f"{fallback_provider} fallback. Reason: {reason}"
        ),
    }


def _provider_error_text(exc: Exception) -> str:
    message = str(exc).strip()
    if len(message) > 280:
        message = f"{message[:277]}..."
    return message or type(exc).__name__


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
    try:
        context_mode = normalize_context_mode(
            body.context_mode
            or load_app_preference(engine, "context_mode", DEFAULT_CONTEXT_MODE)
        )
        active_focus = _active_focus_from_body(body)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    context_bundle = None
    if body.agent_mode in {"neuro_tutor", "neuro_research"}:
        context_bundle = build_context_bundle(
            engine,
            request={
                "mode": context_mode,
                "agent_mode": body.agent_mode,
                "user_message": body.message,
                "active_focus": active_focus,
            },
            knowledge_store=stores["knowledge_store"],
            vector_store=stores["vector_store"],
            context_store=stores["context_store"],
        )

    def build_attempt(excluded: set[str] | None = None) -> AgentAttempt:
        return _build_agent_attempt(
            body.agent_mode,
            engine,
            stores["vector_store"],
            stores["knowledge_store"],
            stores["context_store"],
            providers,
            prior_context,
            context_mode,
            context_bundle,
            chunk_store=stores.get("chunk_store"),
            excluded_providers=excluded,
        )

    try:
        attempt = build_attempt()
    except RoutingError as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    return StreamingResponse(
        _stream_chat(attempt, body.message, history, fallback_factory=build_attempt),
        media_type="text/event-stream",
    )
