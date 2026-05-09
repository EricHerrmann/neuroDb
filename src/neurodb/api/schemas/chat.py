from __future__ import annotations
from typing import Any

from pydantic import BaseModel


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatTurnRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []
    agent_mode: str
