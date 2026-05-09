from pydantic import BaseModel


class PreferencesResponse(BaseModel):
    agent_mode: str
    relevance_threshold: float


class AgentModeUpdate(BaseModel):
    mode: str


class AgentModeResponse(BaseModel):
    agent_mode: str
