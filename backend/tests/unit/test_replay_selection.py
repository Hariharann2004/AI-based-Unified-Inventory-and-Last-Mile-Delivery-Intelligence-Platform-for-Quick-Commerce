import importlib
from copy import deepcopy
from datetime import date

import numpy as np
import pytest
from test_batches import make_batch
from test_ingestion import DELIVERY, INVENTORY, csv_bytes

from unified_intelligence.application.ingestion_service import IngestionService
from unified_intelligence.application.inventory_service import InventoryService
from unified_intelligence.application.replay_demonstration_service import ReplayDemonstrationService
from unified_intelligence.application.replay_service import ReplayService
from unified_intelligence.application.scenario_service import ScenarioService
from unified_intelligence.domain.decisions import UnifiedDecisionPolicy
from unified_intelligence.infrastructure.persistence.case_repository import CaseRepository


class InventoryStub:
    def predict(self, frame):
        return np.full(len(frame), 20.0)

    def predict_proba(self, frame):
        return np.where(frame["Inventory_Level"].to_numpy() == 0, 0.9, 0.1)


@pytest.fixture()
def selection_setup(tmp_path):
    store = CaseRepository(tmp_path / "selection.db")
    rows = [
        {**INVENTORY, "Date": day, "Inventory_Level": stock}
        for day in ["2024-02-01", "2024-01-20", "2024-01-10", "2024-01-01"]
        for stock in [0, 100, 1000]
    ]
    source = IngestionService(store).ingest(csv_bytes(rows), "inventory", "inventory-fixture.csv")
    batch = make_batch(store, tmp_path)
    model = InventoryStub()
    batch.inventory_factory = lambda: InventoryService(model, model)
    return store, batch, source["import_id"]


def test_date_range_is_inclusive_ordered_and_snapshotted(selection_setup):
    store, batch, import_id = selection_setup
    service = ReplayService(store, batch)
    run = service.start(
        "inventory", import_id, 4, start_date=date(2024, 1, 10), end_date="2024-01-20"
    )
    dates = [store.record(record_id)["inputs"]["Date"] for record_id in run["record_ids"]]
    assert dates == ["2024-01-10"] * 3 + ["2024-01-20"]
    assert run["eligible_records"] == 6
    assert run["date_range"] == {"start_date": "2024-01-10", "end_date": "2024-01-20"}
    assert run["selected_dates"] == {"first": "2024-01-10", "last": "2024-01-20"}
    assert service.get(run["run_id"])["record_ids"] == run["record_ids"]
    stepped = service.step(run["run_id"], 0, 1)
    assert stepped["events"][0]["occurred_at"] == "2024-01-10"
    assert store.record(run["record_ids"][0])["inputs"]["Date"] == "2024-01-10"
    assert service.start("inventory", import_id, 20, start_date="2024-01-20")["total"] == 6
    assert service.start("inventory", import_id, 20, end_date="2024-01-10")["total"] == 6
    assert service.start("inventory", import_id, 20)["total"] == 12
    with pytest.raises(ValueError, match="Start date"):
        service.start("inventory", import_id, 2, start_date="2024-02-01", end_date="2024-01-01")
    with pytest.raises(ValueError, match="Date ranges"):
        service.start("delivery", import_id, 2, start_date="2024-01-01")
    with pytest.raises(ValueError, match="selected date range"):
        service.start("inventory", import_id, 2, start_date="2025-01-01")


def test_demo_uses_saved_historical_cases_across_dates_without_writes(selection_setup):
    store, batch, import_id = selection_setup
    records = store.records("inventory")["records"]
    batch.process([record["record_id"] for record in records])
    ScenarioService(store, batch).evaluate("depleted_stock", records[0]["record_id"])
    replay = ReplayService(store, batch)
    run = replay.start("inventory", import_id, 3)
    replay.step(run["run_id"], 0, 3)
    original_cases = store.cases(limit=100)
    original_records = deepcopy(records)
    service = ReplayDemonstrationService(store)
    demo = service.select("inventory", import_id)
    assert demo["available_counts"] == {"Critical": 4, "High": 4, "Normal": 4}
    assert demo["selected_counts"] == {"Critical": 3, "High": 3, "Normal": 3}
    assert not demo["missing_priorities"]
    assert demo["accuracy_evaluation"] is False
    assert demo["representative_sample"] is False
    assert demo["new_predictions"] is False
    assert len({item["record_id"] for item in demo["events"]}) == 9
    assert service.select("inventory", import_id) == demo
    for priority in ["Critical", "High", "Normal"]:
        selected = [item for item in demo["events"] if item["priority"] == priority]
        assert len({item["occurred_at"] for item in selected}) == 3
        assert selected[0]["occurred_at"] == "2024-01-01"
        assert selected[-1]["occurred_at"] == "2024-02-01"
    for event in demo["events"]:
        case = store.case(event["case_id"])
        assert case["priority"] == event["priority"]
        assert case["evidence"]["provenance"] == "historical_dataset"
        assert event["source_position"] == store.record(event["record_id"])["position"]
    assert store.cases(limit=100) == original_cases
    assert store.records("inventory")["records"] == original_records


def test_demo_fills_short_date_ranges_and_deduplicates_model_versions(selection_setup):
    store, batch, import_id = selection_setup
    records = store.records("inventory")["records"]
    batch.process([record["record_id"] for record in records])
    evidence = batch.assess(records[2])
    evidence["models"] = {"version": "new-test-model"}
    evidence["assessment"]["stockout_probability"] = 0.9
    evidence["decision"] = UnifiedDecisionPolicy().evaluate(evidence["assessment"]).to_dict()
    latest = store.save_case(evidence)
    demo = ReplayDemonstrationService(store).select("inventory", import_id, 10)
    assert demo["available_counts"] == {"Critical": 5, "High": 4, "Normal": 3}
    assert len(demo["events"]) == 12
    versions = [item for item in demo["events"] if item["record_id"] == records[2]["record_id"]]
    assert len(versions) == 1
    assert versions[0]["case_id"] == latest["case_id"]
    assert versions[0]["priority"] == "Critical"


def test_demo_reports_absent_groups_and_isolates_imports(selection_setup):
    store, batch, import_id = selection_setup
    service = ReplayDemonstrationService(store)
    empty = service.select("inventory", import_id)
    assert empty["events"] == []
    assert empty["missing_priorities"] == ["Critical", "High", "Normal"]
    delivery = IngestionService(store).ingest(
        csv_bytes([DELIVERY, DELIVERY]), "delivery", "delivery"
    )
    delivery_ids = [row["record_id"] for row in store.records("delivery")["records"]]
    batch.process(delivery_ids)
    demo = service.select("delivery", delivery["import_id"], 3)
    assert demo["available_counts"] == {"Critical": 0, "High": 2, "Normal": 0}
    assert demo["missing_priorities"] == ["Critical", "Normal"]
    assert all(event["occurred_at"] is None for event in demo["events"])
    assert service.select("inventory", import_id)["events"] == []
    with pytest.raises(ValueError, match="matching dataset"):
        service.select("inventory", delivery["import_id"])
    for kind, size in [("unknown", 3), ("inventory", 0), ("inventory", 11)]:
        with pytest.raises(ValueError):
            service.select(kind, import_id, size)


def test_selection_api_validation_and_no_prediction_on_demo(client, monkeypatch, selection_setup):
    store, batch, import_id = selection_setup
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "store", lambda: store)
    monkeypatch.setattr(module, "batch_service", lambda: batch)
    response = client.post(
        "/api/workbench/replays",
        json={
            "kind": "inventory",
            "import_id": import_id,
            "start_date": "2024-01-10",
            "end_date": "2024-01-20",
        },
    )
    assert response.status_code == 201
    assert response.get_json()["total"] == 6
    for updates in [
        {"start_date": "not-a-date"},
        {"start_date": "2024-02-01", "end_date": "2024-01-01"},
        {"kind": "delivery", "start_date": "2024-01-01"},
    ]:
        assert (
            client.post(
                "/api/workbench/replays",
                json={
                    "kind": "inventory",
                    "import_id": import_id,
                    **updates,
                },
            ).status_code
            == 422
        )
    monkeypatch.setattr(module, "batch_service", lambda: pytest.fail("Demo must not predict"))
    url = f"/api/workbench/replay-demonstrations?kind=inventory&import_id={import_id}"
    assert client.get(url).status_code == 200
    assert client.get(url + "&per_priority=11").status_code == 422
    assert client.get("/api/workbench/replay-demonstrations?kind=inventory").status_code == 422
