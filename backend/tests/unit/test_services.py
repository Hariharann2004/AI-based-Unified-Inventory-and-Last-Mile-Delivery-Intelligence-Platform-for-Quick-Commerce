from __future__ import annotations

import numpy as np

from unified_intelligence.application.delivery_service import DeliveryService
from unified_intelligence.application.inventory_service import InventoryService


class RegressionStub:
    def __init__(self, prediction: float):
        self.prediction = prediction

    def predict(self, _frame):
        return np.array([self.prediction])


class ClassificationStub:
    def __init__(self, probability: float):
        self.probability = probability

    def predict_proba(self, _frame):
        return np.array([self.probability])


def test_inventory_service_calculates_reorder_and_health() -> None:
    service = InventoryService(RegressionStub(20), ClassificationStub(0.8))

    result = service.predict({
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
    })

    assert result["predicted_daily_demand"] == 20
    assert result["stockout_risk"] == "High"
    assert result["reorder_required"] is True
    assert result["recommended_reorder_quantity"] == 130
    assert result["recommendation"] == "Reorder immediately"


def test_delivery_service_calculates_scores_and_cost() -> None:
    service = DeliveryService(RegressionStub(25), ClassificationStub(0.4))

    result = service.predict({
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
    })

    assert result["predicted_eta_minutes"] == 25
    assert result["delay_risk"] == "Medium"
    assert result["estimated_delivery_cost"] == 60
    assert result["recommendation"] == "Monitor delivery and prepare an ETA update"
