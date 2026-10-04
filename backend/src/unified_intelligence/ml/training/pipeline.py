from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from unified_intelligence.core.config import PROJECT_ROOT
from unified_intelligence.ml.evaluation import classification_metrics, regression_metrics
from unified_intelligence.ml.features import (
    DELIVERY_FEATURES,
    INVENTORY_FEATURES,
    derive_stockout_target,
    prepare_delivery_features,
    prepare_inventory_features,
)
from unified_intelligence.ml.registry import FileModelRegistry, ModelMetadata, dataset_fingerprint
from unified_intelligence.utils.modeling import LightGBMArtifact


class TrainingPipeline:
    def __init__(
        self, raw_directory: Path, registry: FileModelRegistry, reports_directory: Path
    ) -> None:
        self.raw_directory = raw_directory
        self.registry = registry
        self.reports_directory = reports_directory

    @staticmethod
    def _validate(frame: pd.DataFrame, required: list[str], dataset: str) -> None:
        missing = sorted(set(required) - set(frame.columns))
        if missing:
            raise ValueError(f"{dataset} dataset is missing required columns: {', '.join(missing)}")

    def _train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        *,
        name: str,
        task: str,
        target: str,
        fingerprint: str,
        chronological: bool = False,
    ) -> dict[str, float]:
        if chronological:
            cutoff = int(len(X) * 0.8)
            X_train, X_test = X.iloc[:cutoff], X.iloc[cutoff:]
            y_train, y_test = y.iloc[:cutoff], y.iloc[cutoff:]
        else:
            stratify = (
                y
                if task == "classification" and y.nunique() > 1 and y.value_counts().min() > 1
                else None
            )
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=stratify
            )
        artifact = LightGBMArtifact.train(X_train, y_train, task)  # type: ignore[arg-type]
        metrics = (
            regression_metrics(y_test, artifact.predict(X_test))
            if task == "regression"
            else classification_metrics(y_test, artifact.predict_proba(X_test))
        )
        self.registry.save(
            artifact,
            ModelMetadata(name, task, target, list(X.columns), metrics, fingerprint),
        )
        return metrics

    def run(self) -> dict:
        inventory_path = self.raw_directory / "supply_chain_dataset1.csv"
        delivery_path = self.raw_directory / "Quick_Commerce_Delivery_Logistics.csv"
        inventory = pd.read_csv(inventory_path)
        delivery = pd.read_csv(delivery_path)
        self._validate(inventory, INVENTORY_FEATURES + ["Units_Sold", "Stockout_Flag"], "inventory")
        self._validate(
            delivery, DELIVERY_FEATURES + ["delivery_time_minutes", "delayed"], "delivery"
        )

        inventory["Date"] = pd.to_datetime(inventory["Date"], errors="coerce")
        if inventory["Date"].isna().any():
            raise ValueError("Inventory dataset has invalid dates in the Date column.")
        inventory = inventory.sort_values("Date").reset_index(drop=True)
        stockout_target = derive_stockout_target(inventory)
        if stockout_target.nunique() != 2:
            raise ValueError("Derived stockout-risk target must contain both risk classes.")

        inventory_X = prepare_inventory_features(inventory)
        delivery_X = prepare_delivery_features(delivery)
        inventory_hash = dataset_fingerprint(inventory_path)
        delivery_hash = dataset_fingerprint(delivery_path)
        reports = {
            "inventory_demand": self._train(
                inventory_X,
                inventory["Units_Sold"].astype(float),
                name="inventory_demand",
                task="regression",
                target="Units_Sold",
                fingerprint=inventory_hash,
                chronological=True,
            ),
            "inventory_stockout": self._train(
                inventory_X,
                stockout_target,
                name="inventory_stockout",
                task="classification",
                target="derived_stockout_risk",
                fingerprint=inventory_hash,
            ),
            "delivery_eta": self._train(
                delivery_X,
                delivery["delivery_time_minutes"].astype(float),
                name="delivery_eta",
                task="regression",
                target="delivery_time_minutes",
                fingerprint=delivery_hash,
            ),
            "delivery_delay": self._train(
                delivery_X,
                delivery["delayed"].astype(str).str.lower().eq("yes").astype(int),
                name="delivery_delay",
                task="classification",
                target="delayed",
                fingerprint=delivery_hash,
            ),
            "data_notes": {
                "stockout_flag_source": (
                    "Stockout_Flag was constant at 0; a derived historical risk label "
                    "was used instead."
                ),
                "stockout_risk_rule": (
                    "Inventory_Level < Units_Sold × Supplier_Lead_Time_Days × 1.15"
                ),
                "stockout_risk_positive_rows": int(stockout_target.sum()),
            },
        }
        self.reports_directory.mkdir(parents=True, exist_ok=True)
        (self.reports_directory / "model_metrics.json").write_text(
            json.dumps(reports, indent=2), encoding="utf-8"
        )
        return reports


def main() -> None:
    reports = TrainingPipeline(
        PROJECT_ROOT / "data" / "raw",
        FileModelRegistry(PROJECT_ROOT / "models"),
        PROJECT_ROOT / "reports",
    ).run()
    print(json.dumps(reports, indent=2))
