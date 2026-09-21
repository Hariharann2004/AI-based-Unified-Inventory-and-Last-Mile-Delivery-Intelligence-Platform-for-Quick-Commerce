from pathlib import Path
from typing import Any

import pandas as pd

from unified_intelligence.core.config import Settings, get_settings
from unified_intelligence.domain.inventory import InventoryPolicy
from unified_intelligence.utils.modeling import LightGBMArtifact


class InventoryService:
    def __init__(self, demand_model: Any | None = None, stockout_model: Any | None = None, *, settings: Settings | None = None, demand_path: Path | None = None, stockout_path: Path | None = None, policy: InventoryPolicy | None = None) -> None:
        config = settings or get_settings()
        self.demand_model = demand_model or LightGBMArtifact.load(demand_path or config.model_directory / "inventory_demand.joblib")
        self.stockout_model = stockout_model or LightGBMArtifact.load(stockout_path or config.model_directory / "inventory_stockout.joblib")
        self.policy = policy or InventoryPolicy()

    def predict(self, record: dict[str, Any]) -> dict[str, Any]:
        model_record = dict(record)
        date = pd.to_datetime(model_record.pop("Date"), errors="coerce")
        if pd.isna(date):
            raise ValueError("Date must be a valid date such as 2024-01-01.")
        model_record.update({"year": date.year, "month": date.month, "day_of_week": date.dayofweek})
        frame = pd.DataFrame([model_record])
        demand = float(self.demand_model.predict(frame)[0])
        probability = float(self.stockout_model.predict_proba(frame)[0])
        return self.policy.evaluate(record, demand, probability).to_dict()
