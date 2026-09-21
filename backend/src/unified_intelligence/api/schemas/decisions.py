from __future__ import annotations

from unified_intelligence.api.schemas.common import ApiModel
from unified_intelligence.api.schemas.delivery import (
    DeliveryPredictionRequest,
    DeliveryPredictionResponse,
)
from unified_intelligence.api.schemas.inventory import (
    InventoryPredictionRequest,
    InventoryPredictionResponse,
)


class UnifiedDecisionRequest(ApiModel):
    inventory: InventoryPredictionRequest
    delivery: DeliveryPredictionRequest | None = None


class DecisionResponse(ApiModel):
    operational_priority: str
    assigned_warehouse_only: bool
    actions: list[str]
    summary: str


class UnifiedDecisionResponse(ApiModel):
    inventory: InventoryPredictionResponse
    delivery: DeliveryPredictionResponse | None
    decision: DecisionResponse
