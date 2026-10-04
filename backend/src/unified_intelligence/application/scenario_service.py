from copy import deepcopy

from unified_intelligence.domain.decisions import UnifiedDecisionPolicy

SCENARIOS = [
    {
        "id": "depleted_stock",
        "kind": "inventory",
        "label": "Depleted stock",
        "overrides": {"Inventory_Level": 0},
    },
    {
        "id": "supplier_pressure",
        "kind": "inventory",
        "label": "Extended supplier lead time",
        "overrides": {"Supplier_Lead_Time_Days": 30, "Promotion_Flag": 1},
    },
    {
        "id": "traffic_pressure",
        "kind": "delivery",
        "label": "Peak-hour traffic pressure",
        "overrides": {"Traffic_Level": "High", "Peak_Hour": "Yes", "Rider_Workload": 5},
    },
    {
        "id": "combined_pressure",
        "kind": "unified",
        "label": "Explicit combined stress mapping",
        "overrides": {},
    },
]


class ScenarioService:
    def __init__(self, store, batch):
        self.store, self.batch = store, batch

    def evaluate(self, scenario_id, inventory_id=None, delivery_id=None, mapping_reason=""):
        scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
        if scenario is None:
            raise ValueError("Unknown scenario.")

        def assess(kind, record_id, overrides):
            if not record_id:
                raise ValueError(f"Select a source {kind} record.")
            record = deepcopy(self.store.record(record_id))
            if record["kind"] != kind:
                raise ValueError("Scenario source record kind mismatch.")
            record["inputs"].update(overrides)
            evidence = self.batch.assess(record)
            evidence["provenance"] = "synthetic_scenario:" + scenario_id
            evidence["scenario"] = scenario
            evidence["warnings"].append("Modified inputs: stress test, not accuracy evidence.")
            return evidence

        if scenario["kind"] == "unified":
            if not mapping_reason.strip():
                raise ValueError("Combined scenarios require an explicit mapping reason.")
            inventory = assess("inventory", inventory_id, {"Inventory_Level": 0})
            delivery = assess("delivery", delivery_id, SCENARIOS[2]["overrides"])
            evidence = {
                "record_id": inventory_id + ":" + delivery_id,
                "kind": "unified",
                "inputs": {"inventory": inventory["inputs"], "delivery": delivery["inputs"]},
                "assessment": {
                    "inventory": inventory["assessment"],
                    "delivery": delivery["assessment"],
                },
                "calculations": {
                    "inventory": inventory["calculations"],
                    "delivery": delivery["calculations"],
                },
                "explanations": {
                    "inventory": inventory["explanations"],
                    "delivery": delivery["explanations"],
                },
                "models": {"inventory": inventory["models"], "delivery": delivery["models"]},
                "decision": UnifiedDecisionPolicy()
                .evaluate(inventory["assessment"], delivery["assessment"])
                .to_dict(),
                "provenance": "synthetic_scenario:" + scenario_id,
                "order_linkage": "explicit_simulated_mapping",
                "mapping_reason": mapping_reason,
                "source_record_ids": [inventory_id, delivery_id],
                "scenario": scenario,
                "warnings": [*inventory["warnings"], *delivery["warnings"]],
            }
        else:
            kind = scenario["kind"]
            evidence = assess(
                kind, inventory_id if kind == "inventory" else delivery_id, scenario["overrides"]
            )
        case = self.store.save_case(evidence)
        return {**evidence, "case_id": case["case_id"], "accuracy_evaluation": False}
