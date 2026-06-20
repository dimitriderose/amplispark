from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    success: bool = True
    data: Any | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "amplifi-backend"
    version: str = "1.0.0"
