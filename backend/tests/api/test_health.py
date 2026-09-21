from __future__ import annotations

import importlib

from unified_intelligence.infrastructure.persistence import SQLiteDecisionRepository


def test_health_endpoint_reports_algorithm(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "algorithm": "LightGBM only",
        "environment": "development",
    }


def test_inventory_endpoint_rejects_invalid_schema(client) -> None:
    response = client.post("/api/inventory/predict", json={"Inventory_Level": -1})

    assert response.status_code == 422
    assert response.get_json()["error"] == "Request validation failed."


def test_decision_history_returns_persisted_records(client, monkeypatch, tmp_path) -> None:
    repository = SQLiteDecisionRepository(tmp_path / "history.db")
    stored = repository.save(
        {"SKU_ID": "SKU-1"},
        None,
        {"decision": {"operational_priority": "Normal"}},
    )
    app_module = importlib.import_module("unified_intelligence.api.app")
    monkeypatch.setattr(app_module, "_repository", repository)

    response = client.get("/api/decisions?limit=1")

    assert response.status_code == 200
    assert response.get_json()[0]["decision_id"] == stored.decision_id
