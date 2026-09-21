import pandas as pd

from unified_intelligence.ml.features.common import normalize_categorical_columns

DELIVERY_FEATURES = [
    "delivery_partner", "package_type", "vehicle_type", "delivery_mode", "region",
    "weather_condition", "distance_km", "package_weight_kg", "expected_time_minutes",
    "delivery_rating", "Traffic_Level", "Peak_Hour", "Rider_Workload",
]


def prepare_delivery_features(frame: pd.DataFrame) -> pd.DataFrame:
    return normalize_categorical_columns(frame[DELIVERY_FEATURES])
