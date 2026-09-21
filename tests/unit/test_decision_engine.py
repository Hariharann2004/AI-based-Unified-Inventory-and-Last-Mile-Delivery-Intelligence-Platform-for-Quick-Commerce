from __future__ import annotations

from src.decision_engine.service import create_unified_recommendation


def inventory(probability: float, reorder_required: bool = False) -> dict:
    return {
        "stockout_probability": probability,
        "reorder_required": reorder_required,
    }


def delivery(probability: float) -> dict:
    return {"delay_probability": probability}


def test_normal_decision_has_no_escalation() -> None:
    result = create_unified_recommendation(inventory(0.1), delivery(0.1))

    assert result["operational_priority"] == "Normal"
    assert result["assigned_warehouse_only"] is True
    assert result["actions"] == ["Continue normal inventory and delivery monitoring"]


def test_reorder_required_creates_high_priority_action() -> None:
    result = create_unified_recommendation(inventory(0.3, reorder_required=True))

    assert result["operational_priority"] == "High"
    assert result["actions"] == ["Create a reorder for the assigned warehouse"]


def test_high_stockout_and_delay_risks_are_critical() -> None:
    result = create_unified_recommendation(inventory(0.7), delivery(0.7))

    assert result["operational_priority"] == "Critical"
    assert result["actions"] == [
        "Mark product unavailable at the assigned warehouse",
        "Create an urgent supplier reorder",
        "Notify customer of the revised ETA",
        "Prioritize rider support for this delivery",
    ]


def test_medium_delay_adds_monitoring_action() -> None:
    result = create_unified_recommendation(inventory(0.1), delivery(0.35))

    assert result["operational_priority"] == "Normal"
    assert result["actions"] == ["Monitor the delivery and prepare an ETA update"]

