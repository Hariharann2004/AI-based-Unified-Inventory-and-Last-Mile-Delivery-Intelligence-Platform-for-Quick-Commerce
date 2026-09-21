from collections.abc import Mapping
from typing import Any

from unified_intelligence.domain.delivery.entities import DeliveryAssessment


def _risk_label(probability: float) -> str:
    return "High" if probability >= 0.70 else "Medium" if probability >= 0.35 else "Low"


class DeliveryPolicy:
    """Pure delivery rules applied after model inference."""

    def evaluate(
        self, record: Mapping[str, Any], predicted_eta: float, delay_probability: float
    ) -> DeliveryAssessment:
        eta = max(1.0, float(predicted_eta))
        probability = float(delay_probability)
        expected = float(record["expected_time_minutes"])
        rating = float(record.get("delivery_rating", 3))
        distance = float(record["distance_km"])
        weight = float(record.get("package_weight_kg", 0))
        traffic_charge = {"Low": 0, "Medium": 8, "High": 18}.get(
            str(record.get("Traffic_Level", "Medium")).title(), 8
        )
        vehicle_charge = {"Bike": 0, "Scooter": 4, "Ev Scooter": 2}.get(
            str(record.get("vehicle_type", "Bike")).title(), 0
        )
        estimated_cost = 20 + distance * 7 + weight * 2 + traffic_charge + vehicle_charge
        rider_score = max(
            0.0, min(100.0, rating / 5 * 60 + (1 - probability) * 30 + min(1, expected / eta) * 10)
        )
        intelligence = max(
            0.0, min(100.0, (1 - probability) * 55 + min(1, expected / eta) * 30 + rating / 5 * 15)
        )
        recommendation = "Proceed with normal monitoring"
        if probability >= 0.70:
            recommendation = "Notify customer and update ETA; prioritize rider support"
        elif probability >= 0.35:
            recommendation = "Monitor delivery and prepare an ETA update"

        return DeliveryAssessment(
            delivery_id=record.get("delivery_id"),
            predicted_eta_minutes=round(eta, 1),
            delay_probability=round(probability, 4),
            delay_risk=_risk_label(probability),
            rider_performance_score=round(rider_score, 1),
            estimated_delivery_cost=round(estimated_cost, 2),
            delivery_intelligence_score=round(intelligence, 1),
            recommendation=recommendation,
        )
