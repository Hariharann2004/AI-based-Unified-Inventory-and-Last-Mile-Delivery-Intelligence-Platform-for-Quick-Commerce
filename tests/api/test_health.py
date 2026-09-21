from __future__ import annotations


def test_health_endpoint_reports_algorithm(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "algorithm": "LightGBM only"}

