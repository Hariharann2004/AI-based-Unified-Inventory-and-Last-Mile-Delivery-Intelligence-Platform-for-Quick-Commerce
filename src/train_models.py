"""Train all four approved LightGBM models from the project's raw CSV files.

Run: python -m src.train_models
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, mean_absolute_error, mean_squared_error, roc_auc_score
from sklearn.model_selection import train_test_split

from src.utils.modeling import LightGBMArtifact

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"

INVENTORY_FEATURES = [
    "Date", "SKU_ID", "Warehouse_ID", "Supplier_ID", "Region", "Inventory_Level",
    "Supplier_Lead_Time_Days", "Reorder_Point", "Order_Quantity", "Unit_Cost",
    "Unit_Price", "Promotion_Flag",
]
DELIVERY_FEATURES = [
    "delivery_partner", "package_type", "vehicle_type", "delivery_mode", "region",
    "weather_condition", "distance_km", "package_weight_kg", "expected_time_minutes",
    "delivery_rating", "Traffic_Level", "Peak_Hour", "Rider_Workload",
]


def _prepare(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    result = frame[features].copy()
    for column in result.columns:
        if not pd.api.types.is_numeric_dtype(result[column]):
            result[column] = result[column].fillna("Unknown").astype(str)
    # The date is converted to calendar features; retain no raw date string.
    if "Date" in result:
        dates = pd.to_datetime(result.pop("Date"), errors="coerce")
        result["year"] = dates.dt.year.fillna(0).astype(int)
        result["month"] = dates.dt.month.fillna(0).astype(int)
        result["day_of_week"] = dates.dt.dayofweek.fillna(0).astype(int)
    return result


def _regression_report(y_true: pd.Series, predicted: np.ndarray) -> dict:
    return {
        "mae": round(float(mean_absolute_error(y_true, predicted)), 4),
        "rmse": round(float(mean_squared_error(y_true, predicted) ** 0.5), 4),
    }


def _classification_report(y_true: pd.Series, probability: np.ndarray) -> dict:
    result = {"accuracy": round(float(accuracy_score(y_true, probability >= 0.5)), 4)}
    if y_true.nunique() == 2:
        result["roc_auc"] = round(float(roc_auc_score(y_true, probability)), 4)
    return result


def _derived_stockout_target(inventory: pd.DataFrame) -> pd.Series:
    """Create a learnable historical stockout label.

    The supplied Stockout_Flag is constant (all zero), so it cannot be used as a
    classification target. A past row is labelled risky when its inventory could
    not cover observed demand for the supplier lead time plus a 15% safety buffer.
    Units_Sold is deliberately not an input feature, preventing this target from
    being copied directly at prediction time.
    """
    lead_time_demand = (
        inventory["Units_Sold"].astype(float)
        * inventory["Supplier_Lead_Time_Days"].astype(float)
        * 1.15
    )
    return inventory["Inventory_Level"].astype(float).lt(lead_time_demand).astype(int)


def _train_and_save(
    X: pd.DataFrame, y: pd.Series, task: str, filename: str, chronological: bool = False
) -> dict:
    if chronological:
        cutoff = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:cutoff], X.iloc[cutoff:]
        y_train, y_test = y.iloc[:cutoff], y.iloc[cutoff:]
    else:
        stratify = y if task == "classification" and y.nunique() > 1 and y.value_counts().min() > 1 else None
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=stratify)
    artifact = LightGBMArtifact.train(X_train, y_train, task)  # type: ignore[arg-type]
    artifact.save(MODELS / filename)
    if task == "regression":
        return _regression_report(y_test, artifact.predict(X_test))
    return _classification_report(y_test, artifact.predict_proba(X_test))


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    inventory = pd.read_csv(RAW / "supply_chain_dataset1.csv")
    delivery = pd.read_csv(RAW / "Quick_Commerce_Delivery_Logistics.csv")

    for name, frame, columns in (
        ("inventory", inventory, INVENTORY_FEATURES + ["Units_Sold", "Stockout_Flag"]),
        ("delivery", delivery, DELIVERY_FEATURES + ["delivery_time_minutes", "delayed"]),
    ):
        missing = sorted(set(columns) - set(frame.columns))
        if missing:
            raise ValueError(f"{name} dataset is missing required columns: {', '.join(missing)}")
    inventory["Date"] = pd.to_datetime(inventory["Date"], errors="coerce")
    if inventory["Date"].isna().any():
        raise ValueError("Inventory dataset has invalid dates in the Date column.")
    inventory = inventory.sort_values("Date").reset_index(drop=True)
    stockout_target = _derived_stockout_target(inventory)
    if stockout_target.nunique() != 2:
        raise ValueError("Derived stockout-risk target must contain both risk classes.")

    inv_X = _prepare(inventory, INVENTORY_FEATURES)
    delivery_X = _prepare(delivery, DELIVERY_FEATURES)
    reports = {
        "inventory_demand": _train_and_save(inv_X, inventory["Units_Sold"].astype(float), "regression", "inventory_demand.joblib", chronological=True),
        "inventory_stockout": _train_and_save(inv_X, stockout_target, "classification", "inventory_stockout.joblib"),
        "delivery_eta": _train_and_save(delivery_X, delivery["delivery_time_minutes"].astype(float), "regression", "delivery_eta.joblib"),
        "delivery_delay": _train_and_save(delivery_X, delivery["delayed"].astype(str).str.lower().eq("yes").astype(int), "classification", "delivery_delay.joblib"),
    }
    reports["data_notes"] = {
        "stockout_flag_source": "Stockout_Flag was constant at 0; a derived historical risk label was used instead.",
        "stockout_risk_rule": "Inventory_Level < Units_Sold × Supplier_Lead_Time_Days × 1.15",
        "stockout_risk_positive_rows": int(stockout_target.sum()),
    }
    (REPORTS / "model_metrics.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
