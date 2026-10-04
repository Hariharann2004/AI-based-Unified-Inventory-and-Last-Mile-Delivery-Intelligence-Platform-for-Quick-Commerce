"""Explain individual stored records without inferring cross-dataset order links."""

import hashlib
import time

import pandas as pd

from unified_intelligence.application.ingestion_service import MODELS
from unified_intelligence.domain.decisions import UnifiedDecisionPolicy
from unified_intelligence.ml.features.inventory import prepare_inventory_features


def contribution(model, frame):
    if not hasattr(model, "explain"):
        return {"available": False, "reason": "This model adapter has no contribution support."}
    return model.explain(frame)


def identity(path):
    return {
        "algorithm": "LightGBM",
        "artifact": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
    }


class BatchService:
    def __init__(self, store, inventory_factory, delivery_factory, model_directory):
        self.store = store
        self.inventory_factory = inventory_factory
        self.delivery_factory = delivery_factory
        self.model_directory = model_directory

    def assess(self, record):
        inputs, kind = record["inputs"], record["kind"]
        inputs = MODELS[kind].model_validate(inputs).model_dump(by_alias=True, mode="json")
        if kind == "inventory":
            service = self.inventory_factory()
            assessment = service.predict(inputs)
            frame = prepare_inventory_features(pd.DataFrame([inputs]))
            models = {"demand": service.demand_model, "stockout": service.stockout_model}
            required = (
                assessment["predicted_daily_demand"] * inputs["Supplier_Lead_Time_Days"] * 1.15
            )
            calculations = {
                "current_stock": inputs["Inventory_Level"],
                "required_stock": round(required, 2),
                "reorder_point": inputs["Reorder_Point"],
                "safety_multiplier": 1.15,
                "lead_time_days": inputs["Supplier_Lead_Time_Days"],
                "replenishment_target": round(max(required, inputs["Reorder_Point"] + 1), 2),
                "formula": "demand × lead time × 1.15; refill to at least reorder point + 1",
            }
            decision = UnifiedDecisionPolicy().evaluate(assessment).to_dict()
            warnings = ["Stockout risk uses a derived label, not observed fulfilment failures."]
            names = {"demand": "inventory_demand", "stockout": "inventory_stockout"}
        else:
            service = self.delivery_factory()
            assessment = service.predict(inputs)
            frame = pd.DataFrame([inputs])
            models = {"eta": service.eta_model, "delay": service.delay_model}
            calculations = {
                "expected_minutes": inputs["expected_time_minutes"],
                "predicted_minutes": assessment["predicted_eta_minutes"],
                "distance_km": inputs["distance_km"],
                "formula": "cost = 20 + distance × 7 + weight × 2 + traffic + vehicle",
                "score_note": "Scores are policy formulas; delay and ETA are ML predictions.",
            }
            delay = assessment["delay_probability"]
            decision = {
                "operational_priority": "High" if delay >= 0.7 else "Normal",
                "assigned_warehouse_only": True,
                "actions": [assessment["recommendation"]],
                "recommendation": assessment["recommendation"],
            }
            warnings = ["delivery_rating provenance is unverified; this is retrospective analysis."]
            names = {"eta": "delivery_eta", "delay": "delivery_delay"}
        return {
            "record_id": record["record_id"],
            "import_id": record["import_id"],
            "kind": kind,
            "inputs": inputs,
            "assessment": assessment,
            "decision": decision,
            "calculations": calculations,
            "explanations": {name: contribution(model, frame) for name, model in models.items()},
            "models": {
                name: identity(self.model_directory / (names[name] + ".joblib")) for name in models
            },
            "warnings": warnings,
            "provenance": "historical_dataset",
            "order_linkage": "independent_dataset",
        }

    def process(self, record_ids):
        started = time.monotonic()
        results, failures = [], []
        for record_id in dict.fromkeys(record_ids):
            try:
                results.append(self.assess(self.store.record(record_id)))
            except (KeyError, ValueError, FileNotFoundError) as error:
                failures.append({"record_id": record_id, "error": str(error)})
        return {
            "results": results,
            "failures": failures,
            "processed": len(results),
            "failed": len(failures),
            "duration_ms": round((time.monotonic() - started) * 1000),
            "mode": "historical_batch",
            "order_linkage": "independent_dataset",
        }
