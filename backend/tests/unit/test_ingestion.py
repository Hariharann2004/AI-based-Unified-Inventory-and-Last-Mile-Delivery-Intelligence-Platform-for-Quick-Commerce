import csv
import importlib
import io

import pytest

from unified_intelligence.application.ingestion_service import MAX_BYTES, IngestionService
from unified_intelligence.infrastructure.persistence.workbench_store import WorkbenchStore

INVENTORY = {
    "Date": "2024-01-01",
    "SKU_ID": "SKU_1",
    "Warehouse_ID": "WH_1",
    "Supplier_ID": "SUP_1",
    "Region": "West",
    "Inventory_Level": 100,
    "Supplier_Lead_Time_Days": 10,
    "Reorder_Point": 120,
    "Order_Quantity": 0,
    "Unit_Cost": 10,
    "Unit_Price": 15,
    "Promotion_Flag": 0,
    "Units_Sold": 20,
}
DELIVERY = {
    "delivery_id": "DEL-1",
    "delivery_partner": "partner",
    "package_type": "grocery",
    "vehicle_type": "Bike",
    "delivery_mode": "Instant",
    "region": "west",
    "weather_condition": "clear",
    "distance_km": 4,
    "package_weight_kg": 2,
    "expected_time_minutes": 20,
    "delivery_rating": 4,
    "Traffic_Level": "Medium",
    "Peak_Hour": "No",
    "Rider_Workload": 1,
    "delayed": "no",
    "delivery_time_minutes": 22,
}


def csv_bytes(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


@pytest.fixture()
def work_store(tmp_path):
    return WorkbenchStore(tmp_path / "workbench.db")


@pytest.mark.parametrize("kind,row", [("inventory", INVENTORY), ("delivery", DELIVERY)])
def test_import_round_trip_and_deduplication(work_store, kind, row):
    service = IngestionService(work_store)
    data = csv_bytes(
        [
            row,
            {**row, "Region" if kind == "inventory" else "distance_km": -1}
            if kind == "delivery"
            else {**row, "Inventory_Level": -1},
        ]
    )
    report = service.ingest(data, kind, "fixture")
    assert report["accepted_rows"] == 1
    assert report["rejected_rows"] == 1
    assert report["rejection_samples"][0]["row"] == 3
    assert service.ingest(data, kind, "fixture")["duplicate"]
    assert len(work_store.imports()) == 1
    records = work_store.records(kind, import_id=report["import_id"], limit=1)
    assert records["total"] == 1
    record = work_store.record(records["records"][0]["record_id"])
    assert record["inputs"]["Inventory_Level" if kind == "inventory" else "distance_km"] > 0
    assert "Units_Sold" not in record["inputs"]
    assert work_store.records(kind, offset=1)["records"] == []


@pytest.mark.parametrize(
    "content,kind,match",
    [
        (b"a,b\n1,2", "inventory", "Missing CSV"),
        (b"\xff", "inventory", "UTF-8"),
        (b"", "unknown", "kind must"),
        (b"x" * (MAX_BYTES + 1), "inventory", "limit"),
        (csv_bytes([{**INVENTORY, "Inventory_Level": "nan"}]), "inventory", "no valid"),
    ],
    ids=["columns", "encoding", "kind", "oversized", "nonfinite"],
)
def test_invalid_import_is_not_saved(work_store, content, kind, match):
    with pytest.raises(ValueError, match=match):
        IngestionService(work_store).ingest(content, kind, "fixture")
    assert work_store.imports() == []


def test_workbench_import_api(client, monkeypatch, work_store):
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "store", lambda: work_store)
    response = client.post(
        "/api/workbench/imports/inventory",
        data={
            "file": (io.BytesIO(csv_bytes([INVENTORY])), "inventory.csv"),
        },
    )
    assert response.status_code == 201
    assert client.get("/api/workbench/imports").get_json()[0]["accepted_rows"] == 1
    record = client.get("/api/workbench/records/inventory?limit=1").get_json()["records"][0]
    assert client.get(f"/api/workbench/record/{record['record_id']}").status_code == 200
    assert client.get("/api/workbench/record/missing").status_code == 404
    assert client.get("/api/workbench/records/unknown").status_code == 400
    assert (
        client.get("/api/workbench/records/inventory?warehouse=WH_1&sku=SKU_1").get_json()["total"]
        == 1
    )
    assert client.get("/api/workbench/records/inventory?warehouse=missing").get_json()["total"] == 0


def test_local_import_api_and_missing_artifacts(client, monkeypatch, work_store, tmp_path):
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "store", lambda: work_store)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    assert client.post("/api/workbench/imports/inventory").status_code == 503
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "supply_chain_dataset1.csv").write_bytes(csv_bytes([INVENTORY]))
    assert client.post("/api/workbench/imports/inventory").status_code == 201
    archive = tmp_path / "data" / "archive" / "legacy_delivery"
    archive.mkdir(parents=True)
    (archive / "Quick_Commerce_Delivery_Logistics.csv").write_bytes(csv_bytes([DELIVERY]))
    # Porter is not compatible with the legacy importer and must not be substituted.
    (raw / "Porter_Delivery_Time_Estimation.csv").write_bytes(b"created_at\n2025-01-01\n")
    assert client.post("/api/workbench/imports/delivery").status_code == 201
