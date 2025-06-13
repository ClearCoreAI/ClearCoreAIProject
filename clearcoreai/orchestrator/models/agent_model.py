from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AgentRegistrationRequest(BaseModel):
    agent_name: str
    version: str
    url: str  # Base URL of the agent (to call /metrics, /mood, etc.)

class AgentInfo(BaseModel):
    agent_name: str
    version: str
    url: str
    registered_at: datetime
    aiwaterdrops_consumed: float = Field(default=0.0)
    last_known_mood: Optional[str] = Field(default=None)