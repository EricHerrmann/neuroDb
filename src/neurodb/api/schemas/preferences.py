from pydantic import BaseModel


class PreferencesResponse(BaseModel):
    agent_mode: str
    context_mode: str
    relevance_threshold: float


class AgentModeUpdate(BaseModel):
    mode: str


class AgentModeResponse(BaseModel):
    agent_mode: str


class ContextModeUpdate(BaseModel):
    mode: str


class ContextModeResponse(BaseModel):
    context_mode: str
