import math
from collections.abc import Mapping
from typing import Any

from unified_intelligence.domain.inventory.entities import InventoryAssessment


def _risk_label(probability: float) -> str:
    if probability >= 0.70:
        return "High"
    if probability >= 0.35:
        return "Medium"
    return "Low"


class InventoryPolicy:
    """Pure inventory rules applied after model inference."""

    def evaluate(self, record: Mapping[str, Any], predicted_demand: float, stockout_probability: float) -> InventoryAssessment:
        demand = max(0.0, float(predicted_demand))
        probability = float(stockout_probability)
        inventory = float(record["Inventory_Level"])
        reorder_point = float(record["Reorder_Point"])
        lead_time = max(1.0, float(record["Supplier_Lead_Time_Days"]))
        required_stock = demand * lead_time * 1.15
        reorder_quantity = max(0, math.ceil(required_stock - inventory))
        should_reorder = inventory <= reorder_point or probability >= 0.70
        health = max(0.0, min(100.0, 100 - probability * 55 - max(0, required_stock - inventory) / max(required_stock, 1) * 45))
        health_status = "Healthy" if health >= 70 else "Moderate" if health >= 40 else "Critical"
        recommendation = "Maintain current stock"
        if should_reorder:
            recommendation = "Reorder immediately" if probability >= 0.70 else "Place a reorder soon"

        return InventoryAssessment(
            sku_id=record.get("SKU_ID"), warehouse_id=record.get("Warehouse_ID"),
            predicted_daily_demand=round(demand, 2), stockout_probability=round(probability, 4),
            stockout_risk=_risk_label(probability), reorder_required=should_reorder,
            recommended_reorder_quantity=reorder_quantity if should_reorder else 0,
            inventory_health_score=round(health, 1), inventory_health_status=health_status,
            recommendation=recommendation,
        )
