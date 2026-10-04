from pydantic import Field

from unified_intelligence.api.schemas.common import ApiModel


class BatchRequest(ApiModel):
    record_ids: list[str] = Field(min_length=1, max_length=100)
