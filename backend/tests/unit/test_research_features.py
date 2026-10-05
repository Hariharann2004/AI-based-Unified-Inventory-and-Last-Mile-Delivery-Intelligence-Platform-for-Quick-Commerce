import numpy as np
import pandas as pd
import pytest

from unified_intelligence.ml.features.research_delivery import (
    CATEGORICAL_COLUMNS,
    LOAD_COLUMNS,
    ORDER_NUMERIC_COLUMNS,
    ResearchFeatureEncoder,
    build_research_features,
)


def orders():
    frame = pd.DataFrame(
        {column: [1, 2] for column in [*CATEGORICAL_COLUMNS, *ORDER_NUMERIC_COLUMNS]}
    )
    frame["created_at"] = ["2025-01-06 10:00:00", "2025-01-07 11:00:00"]
    for column in LOAD_COLUMNS:
        frame[column] = [0, 2]
    return frame


def test_allowlist_excludes_future_outcomes_rating_and_unverified_load():
    frame = orders()
    frame["actual_delivery_time"] = "future"
    frame["elapsed_minutes"] = 99
    frame["delivery_rating"] = 5
    frame["delayed"] = "yes"
    original = frame.copy(deep=True)
    result = build_research_features(frame)
    pd.testing.assert_frame_equal(frame, original)
    assert not set(["actual_delivery_time", "elapsed_minutes", "delayed", "delivery_rating"]) & set(
        result
    )
    assert not set(LOAD_COLUMNS) & set(result)
    assert result["source_day_of_week"].tolist() == [0, 1]
    assert result["source_hour"].tolist() == [10, 11]
    assert result["source_month"].tolist() == [1, 1]


def test_invalid_numbers_remain_missing_instead_of_zero():
    frame = orders()
    frame["subtotal"] = [-1, np.inf]
    frame["total_items"] = ["bad", None]
    frame["market_id"] = [None, 2]
    frame["created_at"] = ["bad date", "2025-01-07 11:00:00"]
    result = build_research_features(frame)
    assert result["subtotal"].isna().all()
    assert result["total_items"].isna().all()
    assert result.loc[0, "market_id"] == "__MISSING__"
    assert pd.isna(result.loc[0, "source_hour"])


def test_opt_in_load_ratios_handle_zero_denominator():
    result = build_research_features(orders(), include_load=True)
    assert pd.isna(result.loc[0, "busy_per_onshift_partner"])
    assert result.loc[1, "busy_per_onshift_partner"] == 1
    assert result.loc[1, "backlog_per_onshift_partner"] == 1


def test_encoder_never_learns_validation_categories():
    features = build_research_features(orders())
    encoder = ResearchFeatureEncoder()
    trained = encoder.fit_transform(features.iloc[[0]])
    vocabulary = {key: value.copy() for key, value in encoder.categories.items()}
    validation = encoder.transform(features.iloc[[1]])
    assert encoder.categories == vocabulary
    assert pd.isna(validation.iloc[0]["store_id"])
    assert trained["store_id"].dtype.name == "category"
    assert validation["store_id"].dtype.name == "category"


def test_missing_columns_and_unfitted_encoder_fail_clearly():
    with pytest.raises(ValueError, match="require columns"):
        build_research_features(pd.DataFrame())
    with pytest.raises(ValueError, match="Fit"):
        ResearchFeatureEncoder().transform(pd.DataFrame())
    with pytest.raises(ValueError, match="categorical"):
        ResearchFeatureEncoder().fit(pd.DataFrame({"wrong": [1]}))
    features = build_research_features(orders())
    encoder = ResearchFeatureEncoder().fit(features)
    with pytest.raises(ValueError, match="contract"):
        encoder.transform(features.drop(columns="store_id"))
