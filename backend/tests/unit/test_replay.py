import importlib

import pytest
from test_batches import make_batch
from test_ingestion import DELIVERY, INVENTORY, csv_bytes

from unified_intelligence.application.ingestion_service import IngestionService
from unified_intelligence.application.replay_service import ReplayConflict, ReplayService
from unified_intelligence.application.scenario_service import ScenarioService
from unified_intelligence.domain.decisions import UnifiedDecisionPolicy
from unified_intelligence.infrastructure.persistence.case_repository import CaseRepository


@pytest.fixture()
def replay_setup(tmp_path):
    store = CaseRepository(tmp_path / "replay.db")
    for kind, row in [("inventory", INVENTORY), ("delivery", DELIVERY)]:
        IngestionService(store).ingest(csv_bytes([row, {**row}]), kind, "fixture")
    batch = make_batch(store, tmp_path)
    return store, batch


def test_replay_order_cursor_and_completion(replay_setup):
    store, batch = replay_setup
    service = ReplayService(store, batch)
    import_id = store.records("inventory")["records"][0]["import_id"]
    run = service.start("inventory", import_id, 10)
    step = service.step(run["run_id"], 0, 1)
    assert step["cursor"] == 1
    assert step["events"][0]["record_id"] == run["record_ids"][0]
    with pytest.raises(ReplayConflict):
        service.step(run["run_id"], 0, 1)
    completed = service.step(run["run_id"], 1, 10)
    assert completed["status"] == "completed"
    assert service.step(run["run_id"], 2, 1) == completed
    assert store.cases()["total"] == 2
    with pytest.raises(ValueError):
        service.start("inventory", "missing", 1)
    with pytest.raises(KeyError):
        service.get("missing")


def test_replay_failure_and_model_changes(replay_setup, monkeypatch):
    store, batch = replay_setup
    service = ReplayService(store, batch)
    import_id = store.records("delivery")["records"][0]["import_id"]
    run = service.start("delivery", import_id, 1)
    monkeypatch.setattr(service, "snapshot", lambda: {"changed": "hash"})
    with pytest.raises(ValueError, match="changed"):
        service.step(run["run_id"], 0, 1)
    monkeypatch.setattr(service, "snapshot", lambda: run["model_snapshot"])
    monkeypatch.setattr(batch, "assess", lambda _: (_ for _ in ()).throw(ValueError("bad record")))
    result = service.step(run["run_id"], 0, 1)
    assert result["status"] == "completed_with_errors"
    assert result["events"][0]["error"] == "bad record"


def test_scenarios_preserve_sources_and_require_mapping(replay_setup):
    store, batch = replay_setup
    inventory = store.records("inventory")["records"][0]
    delivery = store.records("delivery")["records"][0]
    service = ScenarioService(store, batch)
    for scenario in ["depleted_stock", "supplier_pressure", "traffic_pressure"]:
        result = service.evaluate(scenario, inventory["record_id"], delivery["record_id"])
        assert result["provenance"].startswith("synthetic_scenario:")
        assert result["accuracy_evaluation"] is False
    assert store.record(inventory["record_id"])["inputs"]["Inventory_Level"] == 100
    with pytest.raises(ValueError, match="mapping"):
        service.evaluate("combined_pressure", inventory["record_id"], delivery["record_id"])
    combined = service.evaluate(
        "combined_pressure",
        inventory["record_id"],
        delivery["record_id"],
        "Review-only simulated mapping",
    )
    assert combined["decision"]["operational_priority"] == "Critical"
    assert combined["order_linkage"] == "explicit_simulated_mapping"
    assert len(store.case(combined["case_id"])["drafts"]) == 2
    for scenario, inv_id in [
        ("unknown", None),
        ("depleted_stock", None),
        ("depleted_stock", delivery["record_id"]),
    ]:
        with pytest.raises(ValueError):
            service.evaluate(scenario, inv_id)


@pytest.mark.parametrize(
    "stockout,delay,reorder,priority",
    [
        (0.1, 0.1, False, "Normal"),
        (0.1, 0.35, False, "Normal"),
        (0.1, 0.6999, False, "Normal"),
        (0.1, 0.7, False, "High"),
        (0.6999, 0.1, False, "Normal"),
        (0.7, 0.1, False, "Critical"),
        (0.1, 0.7, True, "Critical"),
        (0.2, 0.1, True, "High"),
    ],
)
def test_policy_boundary_scenarios(stockout, delay, reorder, priority):
    result = UnifiedDecisionPolicy().evaluate(
        {"stockout_probability": stockout, "reorder_required": reorder},
        {"delay_probability": delay},
    )
    assert result.operational_priority == priority


def test_replay_and_scenario_api(client, monkeypatch, replay_setup):
    store, batch = replay_setup
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "store", lambda: store)
    monkeypatch.setattr(module, "batch_service", lambda: batch)
    import_id = store.records("inventory")["records"][0]["import_id"]
    run = client.post(
        "/api/workbench/replays",
        json={
            "kind": "inventory",
            "import_id": import_id,
            "limit": 2,
        },
    ).get_json()
    url = f"/api/workbench/replays/{run['run_id']}"
    assert client.get(url).status_code == 200
    assert client.post(url + "/steps", json={"expected_cursor": 0}).status_code == 200
    assert client.post(url + "/steps", json={"expected_cursor": 0}).status_code == 409
    assert len(client.get("/api/workbench/scenarios").get_json()) == 4
    response = client.post(
        "/api/workbench/scenarios",
        json={
            "scenario_id": "depleted_stock",
            "inventory_id": run["record_ids"][0],
        },
    )
    assert response.status_code == 200
