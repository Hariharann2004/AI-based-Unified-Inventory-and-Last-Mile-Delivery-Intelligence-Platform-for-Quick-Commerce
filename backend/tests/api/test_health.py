from __future__ import annotations


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
