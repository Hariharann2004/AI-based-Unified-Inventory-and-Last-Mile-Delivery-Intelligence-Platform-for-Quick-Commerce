import pandas as pd

from unified_intelligence.ml.features.common import normalize_categorical_columns

INVENTORY_FEATURES = [
    "Date",
    "SKU_ID",
    "Warehouse_ID",
    "Supplier_ID",
    "Region",
    "Inventory_Level",
    "Supplier_Lead_Time_Days",
    "Reorder_Point",
    "Order_Quantity",
    "Unit_Cost",
    "Unit_Price",
    "Promotion_Flag",
]


def prepare_inventory_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = normalize_categorical_columns(frame[INVENTORY_FEATURES])
    dates = pd.to_datetime(result.pop("Date"), errors="coerce")
    result["year"] = dates.dt.year.fillna(0).astype(int)
    result["month"] = dates.dt.month.fillna(0).astype(int)
    result["day_of_week"] = dates.dt.dayofweek.fillna(0).astype(int)
    return result


def derive_stockout_target(inventory: pd.DataFrame) -> pd.Series:
    """Derive historical risk without leaking Units_Sold into model inputs."""
    lead_time_demand = (
        inventory["Units_Sold"].astype(float)
        * inventory["Supplier_Lead_Time_Days"].astype(float)
        * 1.15
    )
    return inventory["Inventory_Level"].astype(float).lt(lead_time_demand).astype(int)
