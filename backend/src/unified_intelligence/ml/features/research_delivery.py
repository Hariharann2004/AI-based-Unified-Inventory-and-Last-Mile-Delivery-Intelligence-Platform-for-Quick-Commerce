"""Allowlisted order-creation features and training-only categorical vocabularies."""

import numpy as np
import pandas as pd

CATEGORICAL_COLUMNS = ["market_id", "store_id", "store_primary_category", "order_protocol"]
ORDER_NUMERIC_COLUMNS = [
    "total_items",
    "subtotal",
    "num_distinct_items",
    "min_item_price",
    "max_item_price",
]
LOAD_COLUMNS = ["total_onshift_partners", "total_busy_partners", "total_outstanding_orders"]


def build_research_features(inputs: pd.DataFrame, *, include_load: bool = False) -> pd.DataFrame:
    """Ignore all non-allowlisted columns, especially targets and completion timestamps.

    Fleet/load values are excluded by default because their snapshot timing is unverified.
    Source-clock calendar features do not claim a verified local business timezone.
    Invalid/non-finite/negative numeric inputs become missing, never plausible zero values.
    """
    numeric_columns = [*ORDER_NUMERIC_COLUMNS, *(LOAD_COLUMNS if include_load else [])]
    required = [*CATEGORICAL_COLUMNS, *numeric_columns, "created_at"]
    missing = [column for column in required if column not in inputs]
    if missing:
        raise ValueError(f"Research features require columns: {', '.join(missing)}")
    features = inputs[CATEGORICAL_COLUMNS].copy()
    for column in CATEGORICAL_COLUMNS:
        features[column] = features[column].astype("string").fillna("__MISSING__").astype(str)
    for column in numeric_columns:
        numeric = pd.to_numeric(inputs[column], errors="coerce")
        features[column] = numeric.where(np.isfinite(numeric) & (numeric >= 0), np.nan)
    created = pd.to_datetime(inputs["created_at"], format="ISO8601", errors="coerce", utc=True)
    for name, values in {
        "source_hour": created.dt.hour,
        "source_day_of_week": created.dt.dayofweek,
        "source_month": created.dt.month,
    }.items():
        features[name] = values.astype(float)
    if include_load:
        denominator = features["total_onshift_partners"].replace(0, np.nan)
        features["busy_per_onshift_partner"] = features["total_busy_partners"] / denominator
        features["backlog_per_onshift_partner"] = features["total_outstanding_orders"] / denominator
    return features


class ResearchFeatureEncoder:
    """Native LightGBM categories avoid a dense thousands-of-stores one-hot matrix."""

    def __init__(self):
        self.categories: dict[str, list[str]] = {}
        self.columns: list[str] = []

    def fit(self, features: pd.DataFrame):
        if not all(column in features for column in CATEGORICAL_COLUMNS):
            raise ValueError("Encoder requires the allowlisted categorical features.")
        self.columns = list(features.columns)
        self.categories = {
            column: sorted(features[column].unique().tolist()) for column in CATEGORICAL_COLUMNS
        }
        return self

    def transform(self, features: pd.DataFrame) -> pd.DataFrame:
        if not self.columns:
            raise ValueError("Fit the research encoder on training inputs before transform.")
        if list(features.columns) != self.columns:
            raise ValueError("Research feature columns differ from the fitted contract.")
        encoded = features.copy()
        for column, categories in self.categories.items():
            encoded[column] = pd.Categorical(encoded[column], categories=categories)
        return encoded

    def fit_transform(self, features: pd.DataFrame) -> pd.DataFrame:
        return self.fit(features).transform(features)
