from datetime import date
from typing import Literal

from pydantic import Field, model_validator

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
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if (self.start_date or self.end_date) and self.kind != "inventory":
            raise ValueError("Date ranges require inventory records with recorded dates.")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("Start date must be on or before end date.")
        return self


class ReplayDemonstrationRequest(ApiModel):
    kind: Literal["inventory", "delivery"]
    import_id: str = Field(min_length=1)
    per_priority: int = Field(default=3, ge=1, le=10)


class StepRequest(ApiModel):
    expected_cursor: int = Field(ge=0)
    count: int = Field(default=1, ge=1, le=10)


class ScenarioRequest(ApiModel):
    scenario_id: str = Field(min_length=1)
    inventory_id: str | None = None
    delivery_id: str | None = None
    mapping_reason: str = Field(default="", max_length=500)


class EvaluationRequest(ApiModel):
    kind: Literal["inventory", "delivery"]
    import_id: str = Field(min_length=1)


class ProcessingRequest(EvaluationRequest):
    pass


class ResumeProcessingRequest(ApiModel):
    retry_failed: bool = False
