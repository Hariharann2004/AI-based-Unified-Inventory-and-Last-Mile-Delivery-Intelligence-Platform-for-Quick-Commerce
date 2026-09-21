from __future__ import annotations


def create_unified_recommendation(inventory: dict, delivery: dict | None = None) -> dict:
    """Create a transparent operational recommendation without another ML model.

    The selected warehouse is never changed: if it cannot fulfil an order, the
    response explicitly marks it unavailable rather than searching another warehouse.
    """
    stockout = float(inventory["stockout_probability"])
    delivery_delay = float(delivery["delay_probability"]) if delivery else 0.0
    priority = "Normal"
    actions = []

    if stockout >= 0.70:
        priority = "Critical"
        actions += ["Mark product unavailable at the assigned warehouse", "Create an urgent supplier reorder"]
    elif inventory["reorder_required"]:
        priority = "High"
        actions.append("Create a reorder for the assigned warehouse")

    if delivery:
        if delivery_delay >= 0.70:
            priority = "Critical" if priority in {"Critical", "High"} else "High"
            actions += ["Notify customer of the revised ETA", "Prioritize rider support for this delivery"]
        elif delivery_delay >= 0.35:
            actions.append("Monitor the delivery and prepare an ETA update")

    if not actions:
        actions.append("Continue normal inventory and delivery monitoring")
    return {
        "operational_priority": priority,
        "assigned_warehouse_only": True,
        "actions": actions,
        "summary": "; ".join(actions),
    }
