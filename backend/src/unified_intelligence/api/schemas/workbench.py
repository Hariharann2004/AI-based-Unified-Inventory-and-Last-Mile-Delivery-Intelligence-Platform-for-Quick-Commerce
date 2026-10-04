from typing import Literal

from pydantic import Field

from unified_intelligence.api.schemas.common import ApiModel


class BatchRequest(ApiModel):
    record_ids: list[str] = Field(min_length=1, max_length=100)


class ActionRequest(ApiModel):
    action: Literal["approved", "dismissed"]
    actor: str = Field(min_length=1, max_length=80)
    reason: str = Field(default="", max_length=500)


class ReplayRequest(ApiModel):
    kind: Literal["inventory", "delivery"]
    import_id: str = Field(min_length=1)
    limit: int = Field(default=100, ge=1, le=500)


class StepRequest(ApiModel):
    expected_cursor: int = Field(ge=0)
    count: int = Field(default=1, ge=1, le=10)


class ScenarioRequest(ApiModel):
    scenario_id: str = Field(min_length=1)
    inventory_id: str | None = None
    delivery_id: str | None = None
    mapping_reason: str = Field(default="", max_length=500)
