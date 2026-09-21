from collections.abc import Mapping
from typing import Any

from unified_intelligence.domain.decisions.entities import UnifiedDecision


class UnifiedDecisionPolicy:
    """Combine inventory and delivery assessments into explainable actions."""

    def evaluate(self, inventory: Mapping[str, Any], delivery: Mapping[str, Any] | None = None) -> UnifiedDecision:
        stockout = float(inventory["stockout_probability"])
        delivery_delay = float(delivery["delay_probability"]) if delivery else 0.0
        priority = "Normal"
        actions: list[str] = []
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
        return UnifiedDecision(priority, True, actions, "; ".join(actions))
