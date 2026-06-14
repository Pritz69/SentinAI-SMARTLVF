from pydantic import BaseModel
from typing import Optional

class HealthResponse(BaseModel):
    status: str
    project: str
    environment: str
    redis_connected: Optional[bool] = None
    active_sessions: Optional[int] = None
    site_visits: Optional[int] = None