import importlib

import numpy as np
import pandas as pd
import pytest
from test_ingestion import DELIVERY, INVENTORY, csv_bytes

from unified_intelligence.application.batch_service import BatchService
from unified_intelligence.application.delivery_service import DeliveryService
from unified_intelligence.application.ingestion_service import IngestionService
from unified_intelligence.application.inventory_service import InventoryService
from unified_intelligence.core.config import PROJECT_ROOT
from unified_intelligence.domain.inventory import InventoryPolicy
from unified_intelligence.utils.modeling import LightGBMArtifact


class Stub:
    def predict(self, frame):
        return np.full(len(frame), 20.0)

    def predict_proba(self, frame):
        return np.full(len(frame), 0.8)


def make_batch(work_store, tmp_path):
    stub = Stub()
    return BatchService(
        work_store,
        lambda: InventoryService(stub, stub),
        lambda: DeliveryService(stub, stub),
        tmp_path,
    )


def test_batch_independent_records_and_failures(work_store, tmp_path):
    for kind, row in [("inventory", INVENTORY), ("delivery", DELIVERY)]:
        IngestionService(work_store).ingest(csv_bytes([row]), kind, "fixture")
    ids = [work_store.records(k)["records"][0]["record_id"] for k in ["inventory", "delivery"]]
    result = make_batch(work_store, tmp_path).process([*ids, ids[0], "missing"])
    assert result["processed"] == 2
    assert result["failed"] == 1
    assert result["results"][0]["calculations"]["required_stock"] == 230
    assert result["results"][0]["decision"]["operational_priority"] == "Critical"
    assert result["results"][1]["warnings"]
    assert result["order_linkage"] == "independent_dataset"


def test_reorder_point_cannot_produce_zero_quantity():
    result = InventoryPolicy().evaluate(INVENTORY, 1, 0.1)
    assert result.reorder_required
    assert result.recommended_reorder_quantity == 21
    enough = InventoryPolicy().evaluate({**INVENTORY, "Inventory_Level": 1000}, 1, 0.9)
    assert enough.recommended_reorder_quantity == 0
    assert "Review" in enough.recommendation


def test_native_contributions_and_unknown_categories():
    frame = pd.DataFrame({"quantity": np.arange(100), "region": ["west"] * 100})
    model = LightGBMArtifact.train(frame, pd.Series(np.arange(100)), "regression")
    info = model.explain(pd.DataFrame({"quantity": [5], "region": ["new"]}))
    assert info["available"]
    assert info["scale"] == "target_units"
    assert "region_new" in info["unknown_encoded_categories"]
    assert len(info["factors"]) == 2


def test_batch_api_validates_inputs(client, monkeypatch, work_store, tmp_path):
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "batch_service", lambda: make_batch(work_store, tmp_path))
    assert client.post("/api/workbench/batches", json={"record_ids": []}).status_code == 422
    assert client.post("/api/workbench/batches", data="invalid").status_code == 400
    result = client.post("/api/workbench/batches", json={"record_ids": ["missing"]})
    assert result.status_code == 200
    assert result.get_json()["failed"] == 1


@pytest.mark.skipif(
    not (PROJECT_ROOT / "models/inventory_demand.joblib").exists(),
    reason="External model artifacts are optional in CI",
)
def test_local_artifact_batch_explanation(work_store):
    for kind, row in [("inventory", INVENTORY), ("delivery", DELIVERY)]:
        IngestionService(work_store).ingest(csv_bytes([row]), kind, "fixture")
    service = BatchService(work_store, InventoryService, DeliveryService, PROJECT_ROOT / "models")
    ids = [work_store.records(k)["records"][0]["record_id"] for k in ["inventory", "delivery"]]
    result = service.process(ids)
    assert result["failed"] == 0
    assert result["processed"] == 2
    assert result["results"][0]["explanations"]["stockout"]["scale"] == "log_odds"
