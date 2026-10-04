from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ErrorResponse(ApiModel):
    error: str
    details: list[dict] | None = None


class HealthResponse(ApiModel):
    status: str
    algorithm: str
    environment: str
