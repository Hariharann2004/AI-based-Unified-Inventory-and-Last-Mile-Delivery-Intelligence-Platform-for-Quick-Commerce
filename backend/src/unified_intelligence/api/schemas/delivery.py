from __future__ import annotations

from pydantic import Field

from unified_intelligence.api.schemas.common import ApiModel


class DeliveryPredictionRequest(ApiModel):
    delivery_id: str | None = None
    delivery_partner: str = Field(min_length=1)
    package_type: str = Field(min_length=1)
    vehicle_type: str = Field(min_length=1)
    delivery_mode: str = Field(min_length=1)
    region: str = Field(min_length=1)
    weather_condition: str = Field(min_length=1)
    distance_km: float = Field(gt=0)
    package_weight_kg: float = Field(ge=0)
    expected_time_minutes: float = Field(gt=0)
    delivery_rating: float = Field(default=3, ge=0, le=5)
    traffic_level: str = Field(alias="Traffic_Level", min_length=1)
    peak_hour: str = Field(alias="Peak_Hour", min_length=1)
    rider_workload: float = Field(alias="Rider_Workload", ge=0)


class DeliveryPredictionResponse(ApiModel):
    delivery_id: str | None
    predicted_eta_minutes: float
    delay_probability: float
    delay_risk: str
    rider_performance_score: float
    estimated_delivery_cost: float
    delivery_intelligence_score: float
    recommendation: str
