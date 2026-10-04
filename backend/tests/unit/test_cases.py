import importlib

import pytest
from test_batches import make_batch
from test_ingestion import INVENTORY, csv_bytes

from unified_intelligence.application.ingestion_service import IngestionService
from unified_intelligence.infrastructure.persistence.case_repository import CaseRepository


def evidence(kind="inventory", priority="High", quantity=20):
    return {
        "record_id": "fixture:0",
        "inputs": {"stock": 10},
        "models": {"version": "test"},
        "provenance": "historical_dataset",
        "kind": kind,
        "assessment": {
            "reorder_required": True,
            "recommended_reorder_quantity": quantity,
            "warehouse_id": "WH_1",
            "delay_probability": 0.8,
            "predicted_eta_minutes": 25,
        },
        "decision": {"operational_priority": priority},
    }


@pytest.fixture()
def case_store(tmp_path):
    return CaseRepository(tmp_path / "cases.db")


def test_case_dedup_priority_and_approval(case_store):
    first = case_store.save_case(evidence())
    assert case_store.save_case(evidence())["case_id"] == first["case_id"]
    second = case_store.save_case({**evidence("delivery", "Critical"), "record_id": "fixture:1"})
    assert case_store.cases()["cases"][0]["case_id"] == second["case_id"]
    assert case_store.cases(kind="inventory", status="open")["total"] == 1
    approved = case_store.transition(first["case_id"], "approved", "reviewer", "checked")
    assert approved["drafts"][0]["status"] == "approved"
    assert approved["drafts"][0]["external_execution"] is False
    case_store.transition(first["case_id"], "approved", "reviewer", "retry")
    assert len(case_store.case(first["case_id"])["audit"]) == 2
    with pytest.raises(ValueError, match="already reviewed"):
        case_store.transition(first["case_id"], "dismissed", "reviewer", "changed")


def test_case_dismissal_and_review_validation(case_store):
    case = case_store.save_case(evidence(quantity=0))
    assert case["drafts"][0]["type"] == "stock_risk_review"
    for action, actor, reason in [
        ("bad", "x", "x"),
        ("dismissed", "", "x"),
        ("dismissed", "x", ""),
    ]:
        with pytest.raises(ValueError):
            case_store.transition(case["case_id"], action, actor, reason)
    result = case_store.transition(case["case_id"], "dismissed", "reviewer", "duplicate")
    assert result["audit"][-1]["reason"] == "duplicate"
    with pytest.raises(KeyError):
        case_store.case("missing")
    with pytest.raises(KeyError):
        case_store.transition("missing", "approved", "reviewer", "")
    normal = evidence()
    normal["assessment"]["reorder_required"] = False
    normal["record_id"] = "fixture:2"
    case = case_store.save_case(normal)
    with pytest.raises(ValueError, match="no action"):
        case_store.transition(case["case_id"], "approved", "reviewer", "")


def test_case_api(client, monkeypatch, case_store):
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "store", lambda: case_store)
    case = case_store.save_case(evidence())
    assert client.get("/api/workbench/cases?status=open").get_json()["total"] == 1
    assert client.get(f"/api/workbench/cases/{case['case_id']}").status_code == 200
    response = client.post(
        f"/api/workbench/cases/{case['case_id']}/actions",
        json={
            "action": "approved",
            "actor": "reviewer",
        },
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "approved"


def test_batch_creates_persistent_case(case_store, tmp_path):
    IngestionService(case_store).ingest(csv_bytes([INVENTORY]), "inventory", "fixture")
    record_id = case_store.records("inventory")["records"][0]["record_id"]
    result = make_batch(case_store, tmp_path).process([record_id])
    assert result["results"][0]["case_id"]
    assert case_store.cases()["total"] == 1
