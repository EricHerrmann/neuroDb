from __future__ import annotations

from pydantic import BaseModel


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatTurnRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []
    agent_mode: str
    context_mode: str | None = None
    active_focus_type: str | None = None
    active_focus_id: int | None = None
