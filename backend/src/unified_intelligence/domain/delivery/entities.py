from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DeliveryAssessment:
    delivery_id: str | None
    predicted_eta_minutes: float
    delay_probability: float
    delay_risk: str
    rider_performance_score: float
    estimated_delivery_cost: float
    delivery_intelligence_score: float
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
