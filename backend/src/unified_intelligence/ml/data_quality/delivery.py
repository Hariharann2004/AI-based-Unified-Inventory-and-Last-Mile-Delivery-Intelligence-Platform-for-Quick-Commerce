"""Aggregate diagnostics for the legacy quick-commerce delivery CSV contract."""

import numpy as np
import pandas as pd

from unified_intelligence.ml.features.delivery import DELIVERY_FEATURES

AUDIT_FEATURES = [column for column in DELIVERY_FEATURES if column != "delivery_rating"]
REQUIRED_COLUMNS = [*AUDIT_FEATURES, "delivery_time_minutes", "delayed"]
NUMERIC_COLUMNS = [
    "distance_km",
    "package_weight_kg",
    "expected_time_minutes",
    "Rider_Workload",
    "delivery_time_minutes",
    "delivery_rating",
]
SEGMENT_COLUMNS = ["Traffic_Level", "Peak_Hour", "Rider_Workload", "weather_condition"]


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _numeric_profile(series: pd.Series) -> tuple[pd.Series, pd.Series, dict]:
    missing = series.isna() | series.astype("string").str.strip().eq("").fillna(False)
    numeric = pd.to_numeric(series, errors="coerce")
    finite = numeric.notna() & np.isfinite(numeric)
    valid = finite & (numeric >= 0)
    return (
        numeric,
        valid,
        {
            "missing": int(missing.sum()),
            "non_numeric": int((numeric.isna() & ~missing).sum()),
            "non_finite": int((numeric.notna() & ~finite).sum()),
            "negative": int((finite & (numeric < 0)).sum()),
            "valid_nonnegative": int(valid.sum()),
        },
    )


def _segment_rates(frame: pd.DataFrame, column: str, labels: pd.Series) -> list[dict]:
    groups = pd.DataFrame({"segment": frame[column], "label": labels}).groupby(
        "segment", dropna=False, sort=True
    )
    result = []
    for value, group in groups:
        valid_count = int(group["label"].notna().sum())
        delayed_count = int(group["label"].eq(1).sum())
        result.append(
            {
                "value": None if pd.isna(value) else str(value),
                "rows": len(group),
                "valid_labels": valid_count,
                "delayed": delayed_count,
                "delay_rate": _ratio(delayed_count, valid_count),
            }
        )
    return result


def audit_delivery_frame(frame: pd.DataFrame) -> dict:
    """Return JSON-safe aggregates without changing the caller's data.

    Missing columns and invalid rows are reported, not imputed or silently removed.
    The time comparison is a diagnostic hypothesis, not a replacement delay label.
    Counts use explicit denominators; an empty population produces null, not zero.
    """
    if not frame.columns.is_unique:
        raise ValueError("Delivery audit requires unique column names.")
    warnings = [
        "Source collection method and delayed-label definition require source documentation.",
        "These are full-dataset diagnostics, not held-out model accuracy or causal evidence.",
        "delivery_rating availability before prediction is unverified; exclude it from evaluation.",
        "Serving models and original targets remain unchanged by this audit.",
    ]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame]
    if missing_columns:
        warnings.append("Required legacy-contract columns are missing; see missing_columns.")
    labels = pd.Series(np.nan, index=frame.index, dtype=float)
    if "delayed" in frame:
        labels = frame["delayed"].astype("string").str.strip().str.lower().map({"yes": 1, "no": 0})
    valid_count = int(labels.notna().sum())
    delayed_count = int(labels.eq(1).sum())
    on_time_count = int(labels.eq(0).sum())
    numeric_profiles = {}
    numeric_values, numeric_valid = {}, {}
    for column in NUMERIC_COLUMNS:
        if column in frame:
            values, valid, profile = _numeric_profile(frame[column])
            numeric_values[column], numeric_valid[column] = values, valid
            numeric_profiles[column] = profile
    time_comparison = None
    time_columns = ["delivery_time_minutes", "expected_time_minutes"]
    if all(column in numeric_values for column in time_columns):
        valid = labels.notna() & numeric_valid[time_columns[0]] & numeric_valid[time_columns[1]]
        breach = numeric_values[time_columns[0]] > numeric_values[time_columns[1]]
        agreements = int((valid & breach.eq(labels.eq(1))).sum())
        compared = int(valid.sum())
        time_comparison = {
            "hypothesis": "delayed == (delivery_time_minutes > expected_time_minutes)",
            "compared_rows": compared,
            "excluded_rows": len(frame) - compared,
            "agreements": agreements,
            "agreement_rate": _ratio(agreements, compared),
            "contingency": [
                {
                    "actual_exceeds_expected": actual_exceeds,
                    "label": label,
                    "rows": int((valid & breach.eq(actual_exceeds) & labels.eq(value)).sum()),
                }
                for actual_exceeds in [False, True]
                for label, value in [("No", 0), ("Yes", 1)]
            ],
            "interpretation": "Disagreement is not proof of bad data; verify the label definition.",
        }
    feature_groups = None
    if all(column in frame for column in AUDIT_FEATURES):
        hashes = pd.util.hash_pandas_object(frame[AUDIT_FEATURES], index=False)
        counts = pd.DataFrame({"group": hashes, "label": labels}).groupby("group")["label"]
        feature_groups = {
            "features": AUDIT_FEATURES,
            "distinct_input_groups": int(hashes.nunique()),
            "duplicate_input_rows_beyond_first": int(hashes.duplicated().sum()),
            "groups_with_conflicting_valid_labels": int((counts.nunique() > 1).sum()),
        }
    if any(
        profile["missing"] or profile["non_numeric"] or profile["non_finite"] or profile["negative"]
        for profile in numeric_profiles.values()
    ):
        warnings.append("Numeric quality issues exist; inspect numeric_profiles before training.")
    return {
        "schema_version": 1,
        "audit_kind": "legacy_delivery_contract",
        "rows": len(frame),
        "columns": list(frame.columns),
        "missing_columns": missing_columns,
        "missing_cells_by_column": {
            column: int(
                (frame[column].isna() | frame[column].astype("string").str.strip().eq("")).sum()
            )
            for column in frame
        },
        "duplicate_rows_beyond_first": int(frame.duplicated().sum()),
        "numeric_profiles": numeric_profiles,
        "target": {
            "definition_status": "unverified",
            "valid_labels": valid_count,
            "invalid_or_missing_labels": len(frame) - valid_count,
            "delayed": delayed_count,
            "not_delayed": on_time_count,
            "delay_rate": _ratio(delayed_count, valid_count),
            "majority_baseline_accuracy": _ratio(max(delayed_count, on_time_count), valid_count),
            "baseline_scope": "Descriptive full-dataset prevalence, not a held-out test score.",
        },
        "time_label_comparison": time_comparison,
        "input_groups": feature_groups,
        "segment_delay_rates": {
            column: _segment_rates(frame, column, labels)
            for column in SEGMENT_COLUMNS
            if column in frame
        },
        "rating_delay_rates": (
            _segment_rates(frame, "delivery_rating", labels) if "delivery_rating" in frame else None
        ),
        "warnings": warnings,
    }
