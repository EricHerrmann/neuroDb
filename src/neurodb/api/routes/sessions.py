"""GET /api/sessions route."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.sessions import ChatSessionItem
from neurodb.db import get_session
from neurodb.schema import ChatSession

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class EndSessionRequest(BaseModel):
    messages: list[ChatMessage]
    agent_mode: str = "local_db"


class ActiveContextResponse(BaseModel):
    active_prior_topic: str | None = None


@router.get("/sessions", response_model=list[ChatSessionItem])
def get_sessions(engine: Engine = Depends(get_engine)) -> list[ChatSessionItem]:
    with get_session(engine) as session:
        rows = (
            session.query(ChatSession)
            .order_by(ChatSession.started_at.desc())
            .all()
        )
        return [ChatSessionItem.model_validate(r) for r in rows]


@router.get("/sessions/active-context", response_model=ActiveContextResponse)
def get_active_context(
    request: Request,
    engine: Engine = Depends(get_engine),
) -> ActiveContextResponse:
    manager = getattr(request.app.state, "session_manager", None)
    if manager is not None:
        _context, topic = manager.get_most_recent_session_info(engine)
        return ActiveContextResponse(active_prior_topic=topic or None)

    with get_session(engine) as session:
        row = (
            session.query(ChatSession)
            .order_by(ChatSession.started_at.desc())
            .first()
        )
        return ActiveContextResponse(
            active_prior_topic=row.inferred_topic if row is not None else None
        )


def _classify_topic(first_user: str, agent_mode: str) -> str | None:
    try:
        from neurodb.config.provider_factory import build_provider_clients
        from neurodb.config.task_router import TaskRouter

        providers = build_provider_clients()
        if not providers:
            return None
        route = TaskRouter(providers).route("summary.session")
        response = route.model_client.create_message(
            model=route.model_id,
            max_tokens=16,
            system="",
            tools=[],
            messages=[{
                "role": "user",
                "content": (
                    "Assign a short topic category (2–4 words) to this neuroscience chat session.\n"
                    f"Agent mode: {agent_mode}\n"
                    f"First message: {first_user[:300]}\n\n"
                    "Reply with only the category label. Examples: brain plasticity, dataset ingest, "
                    "hypothesis review, data query, literature search."
                ),
            }],
        )
        for block in response.content:
            if block.type == "text":
                return block.text.strip()[:64]
    except Exception:
        pass
    return None


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    engine: Engine = Depends(get_engine),
) -> None:
    with get_session(engine) as session:
        row = session.query(ChatSession).filter_by(session_id=session_id).one_or_none()
        if row is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        session.delete(row)
        session.flush()


@router.post("/sessions/{session_id}/end", response_model=ChatSessionItem)
def end_session(
    session_id: str,
    body: EndSessionRequest,
    request: Request,
    engine: Engine = Depends(get_engine),
) -> ChatSessionItem:
    api_messages = [message.model_dump() for message in body.messages]
    user_turns = sum(1 for message in api_messages if message["role"] == "user")
    first_user = next(
        (
            message["content"]
            for message in api_messages
            if message["role"] == "user" and isinstance(message["content"], str)
        ),
        "unknown",
    )

    summary = None
    manager = getattr(request.app.state, "session_manager", None)
    if manager is not None and user_turns >= 3:
        summary = manager.end_session(session_id, api_messages)

    topic_category = _classify_topic(first_user, body.agent_mode) if user_turns >= 1 else None

    now = datetime.now(UTC).isoformat()
    with get_session(engine) as session:
        row = session.query(ChatSession).filter_by(session_id=session_id).one_or_none()
        if row is None:
            row = ChatSession(
                session_id=session_id,
                inferred_topic=first_user[:200],
                agent_mode=body.agent_mode,
                started_at=now,
                ended_at=now,
                summary_preview=summary[:200] if summary else None,
                message_count=user_turns,
                topic_category=topic_category,
            )
            session.add(row)
            session.flush()
        else:
            row.inferred_topic = first_user[:200]
            row.agent_mode = body.agent_mode
            row.ended_at = now
            row.summary_preview = summary[:200] if summary else row.summary_preview
            row.message_count = user_turns
            if topic_category:
                row.topic_category = topic_category
            session.flush()
        return ChatSessionItem.model_validate(row)
