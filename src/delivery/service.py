from __future__ import annotations

from pathlib import Path
import pandas as pd

from src.utils.modeling import LightGBMArtifact

ROOT = Path(__file__).resolve().parents[2]
ETA_MODEL = ROOT / "models" / "delivery_eta.joblib"
DELAY_MODEL = ROOT / "models" / "delivery_delay.joblib"


def _risk_label(probability: float) -> str:
    return "High" if probability >= 0.70 else "Medium" if probability >= 0.35 else "Low"


class DeliveryService:
    def __init__(self, eta_path: Path = ETA_MODEL, delay_path: Path = DELAY_MODEL):
        self.eta_model = LightGBMArtifact.load(eta_path)
        self.delay_model = LightGBMArtifact.load(delay_path)

    def predict(self, record: dict) -> dict:
        frame = pd.DataFrame([record])
        eta = max(1.0, float(self.eta_model.predict(frame)[0]))
        delay_probability = float(self.delay_model.predict_proba(frame)[0])
        expected = float(record["expected_time_minutes"])
        rating = float(record.get("delivery_rating", 3))
        distance = float(record["distance_km"])
        weight = float(record.get("package_weight_kg", 0))
        traffic_charge = {"Low": 0, "Medium": 8, "High": 18}.get(str(record.get("Traffic_Level", "Medium")).title(), 8)
        vehicle_charge = {"Bike": 0, "Scooter": 4, "Ev Scooter": 2}.get(str(record.get("vehicle_type", "Bike")).title(), 0)
        estimated_cost = 20 + distance * 7 + weight * 2 + traffic_charge + vehicle_charge
        rider_score = max(0.0, min(100.0, rating / 5 * 60 + (1 - delay_probability) * 30 + min(1, expected / eta) * 10))
        intelligence = max(0.0, min(100.0, (1 - delay_probability) * 55 + min(1, expected / eta) * 30 + rating / 5 * 15))
        recommendation = "Proceed with normal monitoring"
        if delay_probability >= 0.70:
            recommendation = "Notify customer and update ETA; prioritize rider support"
        elif delay_probability >= 0.35:
            recommendation = "Monitor delivery and prepare an ETA update"

        return {
            "delivery_id": record.get("delivery_id"),
            "predicted_eta_minutes": round(eta, 1),
            "delay_probability": round(delay_probability, 4),
            "delay_risk": _risk_label(delay_probability),
            "rider_performance_score": round(rider_score, 1),
            "estimated_delivery_cost": round(estimated_cost, 2),
            "delivery_intelligence_score": round(intelligence, 1),
            "recommendation": recommendation,
        }
