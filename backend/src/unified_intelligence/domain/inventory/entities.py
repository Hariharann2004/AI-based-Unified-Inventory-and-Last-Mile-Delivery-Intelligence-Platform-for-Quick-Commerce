from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InventoryAssessment:
    sku_id: str | None
    warehouse_id: str | None
    predicted_daily_demand: float
    stockout_probability: float
    stockout_risk: str
    reorder_required: bool
    recommended_reorder_quantity: int
    inventory_health_score: float
    inventory_health_status: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
