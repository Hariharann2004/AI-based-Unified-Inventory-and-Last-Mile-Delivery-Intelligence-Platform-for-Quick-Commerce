from __future__ import annotations

from pathlib import Path
import math
import pandas as pd

from src.utils.modeling import LightGBMArtifact

ROOT = Path(__file__).resolve().parents[2]
DEMAND_MODEL = ROOT / "models" / "inventory_demand.joblib"
STOCKOUT_MODEL = ROOT / "models" / "inventory_stockout.joblib"


def _risk_label(probability: float) -> str:
    if probability >= 0.70:
        return "High"
    if probability >= 0.35:
        return "Medium"
    return "Low"


class InventoryService:
    def __init__(self, demand_path: Path = DEMAND_MODEL, stockout_path: Path = STOCKOUT_MODEL):
        self.demand_model = LightGBMArtifact.load(demand_path)
        self.stockout_model = LightGBMArtifact.load(stockout_path)

    def predict(self, record: dict) -> dict:
        # Match the calendar feature engineering performed during model training.
        model_record = dict(record)
        date = pd.to_datetime(model_record.pop("Date"), errors="coerce")
        if pd.isna(date):
            raise ValueError("Date must be a valid date such as 2024-01-01.")
        model_record.update({"year": date.year, "month": date.month, "day_of_week": date.dayofweek})
        frame = pd.DataFrame([model_record])
        demand = max(0.0, float(self.demand_model.predict(frame)[0]))
        stockout_probability = float(self.stockout_model.predict_proba(frame)[0])
        inventory = float(record["Inventory_Level"])
        reorder_point = float(record["Reorder_Point"])
        lead_time = max(1.0, float(record["Supplier_Lead_Time_Days"]))

        # Demand is daily. Keep enough stock for lead time plus a 15% safety buffer.
        required_stock = demand * lead_time * 1.15
        reorder_quantity = max(0, math.ceil(required_stock - inventory))
        should_reorder = inventory <= reorder_point or stockout_probability >= 0.70
        health = max(0.0, min(100.0, 100 - stockout_probability * 55 - max(0, required_stock - inventory) / max(required_stock, 1) * 45))
        health_status = "Healthy" if health >= 70 else "Moderate" if health >= 40 else "Critical"

        recommendation = "Maintain current stock"
        if should_reorder:
            recommendation = "Reorder immediately" if stockout_probability >= 0.70 else "Place a reorder soon"

        return {
            "sku_id": record.get("SKU_ID"),
            "warehouse_id": record.get("Warehouse_ID"),
            "predicted_daily_demand": round(demand, 2),
            "stockout_probability": round(stockout_probability, 4),
            "stockout_risk": _risk_label(stockout_probability),
            "reorder_required": should_reorder,
            "recommended_reorder_quantity": reorder_quantity if should_reorder else 0,
            "inventory_health_score": round(health, 1),
            "inventory_health_status": health_status,
            "recommendation": recommendation,
        }
