"""Chronological ETA research, validation-only tuning and no serving artifact writes."""

import hashlib
from importlib.metadata import version

import numpy as np
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

from unified_intelligence.ml.features.research_delivery import (
    ResearchFeatureEncoder,
    build_research_features,
)

CONFIGURATIONS = [
    {"name": "standard", "num_leaves": 31, "min_child_samples": 20, "reg_lambda": 0.0},
    {"name": "regularized", "num_leaves": 15, "min_child_samples": 100, "reg_lambda": 10.0},
    {"name": "shallow", "num_leaves": 7, "min_child_samples": 100, "reg_lambda": 20.0},
]


def chronological_partition(dataset, fraction: float = 1.0):
    if not 0 < fraction <= 1:
        raise ValueError("Window fraction must be greater than zero and at most one.")
    dates = dataset.created_at.dt.floor("D")
    available = sorted(dates.unique())[: int(dates.nunique() * fraction)]
    if len(available) < 10:
        raise ValueError("Research evaluation requires at least ten whole dates in each window.")
    train_end, validation_end = int(len(available) * 0.6), int(len(available) * 0.8)
    validation_start, test_start = available[train_end], available[validation_end]
    train_date_mask = dates.isin(available[:train_end])
    validation_date_mask = dates.isin(available[train_end:validation_end])
    # Outcomes from not-yet-completed deliveries would be unavailable at model/tuning cutoffs.
    train_mask = train_date_mask & (dataset.completed_at < validation_start)
    validation_mask = validation_date_mask & (dataset.completed_at < test_start)
    masks = [train_mask, validation_mask, dates.isin(available[validation_end:])]
    partitions = tuple(np.flatnonzero(mask.to_numpy()) for mask in masks)
    if min(map(len, partitions)) < 2:
        raise ValueError(
            "Research train, validation and test partitions each require two outcomes."
        )
    return partitions, {
        "fraction": fraction,
        "whole_source_dates": len(available),
        "validation_start": str(validation_start),
        "test_start": str(test_start),
        "purged_unavailable_training_outcomes": int((train_date_mask & ~train_mask).sum()),
        "purged_unavailable_validation_outcomes": int(
            (validation_date_mask & ~validation_mask).sum()
        ),
    }


def eta_metrics(observed, predicted):
    observed, predicted = np.asarray(observed, dtype=float), np.asarray(predicted, dtype=float)
    if observed.shape != predicted.shape or not np.isfinite(predicted).all():
        raise ValueError("Research predictions must be finite and match the observed target shape.")
    absolute_error = np.abs(observed - predicted)
    return {
        "rows": len(observed),
        "mae_minutes": float(mean_absolute_error(observed, predicted)),
        "rmse_minutes": float(root_mean_squared_error(observed, predicted)),
        "r2": float(r2_score(observed, predicted))
        if len(observed) > 1 and np.ptp(observed)
        else None,
        "median_absolute_error_minutes": float(np.median(absolute_error)),
        "within_5_minutes_fraction": float((absolute_error <= 5).mean()),
        "within_10_minutes_fraction": float((absolute_error <= 10).mean()),
    }


def train_candidate(features, target, configuration):
    model = LGBMRegressor(
        objective="regression_l1",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=configuration["num_leaves"],
        min_child_samples=configuration["min_child_samples"],
        reg_lambda=configuration["reg_lambda"],
        random_state=42,
        n_jobs=2,
        verbosity=-1,
        deterministic=True,
        force_col_wise=True,
    )
    return model.fit(features, target)


def run_research_window(dataset, *, fraction=1.0, include_load=False, trainer=train_candidate):
    (train, validation, test), partition_metadata = chronological_partition(dataset, fraction)
    features = build_research_features(dataset.inputs, include_load=include_load)
    encoder = ResearchFeatureEncoder()
    train_features = encoder.fit_transform(features.iloc[train])
    validation_features = encoder.transform(features.iloc[validation])
    candidates, selected_model, best_error = [], None, float("inf")
    selected_configuration = None
    for configuration in CONFIGURATIONS:
        model = trainer(train_features, dataset.elapsed_minutes.iloc[train], configuration.copy())
        validation_metrics = eta_metrics(
            dataset.elapsed_minutes.iloc[validation], model.predict(validation_features)
        )
        candidates.append({"configuration": configuration.copy(), "validation": validation_metrics})
        if validation_metrics["mae_minutes"] < best_error:
            best_error = validation_metrics["mae_minutes"]
            selected_model, selected_configuration = model, configuration.copy()
    # Test predictions are requested only after all candidate choices are frozen.
    test_features = encoder.transform(features.iloc[test])
    predictions = np.asarray(selected_model.predict(test_features), dtype=float)
    observed = dataset.elapsed_minutes.iloc[test]
    baseline_mean = float(dataset.elapsed_minutes.iloc[train].mean())
    baseline_median = float(dataset.elapsed_minutes.iloc[train].median())
    known_store = features.iloc[test]["store_id"].isin(encoder.categories["store_id"]).to_numpy()
    weekday = dataset.created_at.iloc[test].dt.dayofweek.to_numpy() < 5
    extreme = observed.to_numpy() > 180
    case_masks = {
        "seen_store": known_store,
        "unseen_store": ~known_store,
        "source_clock_weekday": weekday,
        "source_clock_weekend": ~weekday,
        "observed_duration_at_most_180_minutes": ~extreme,
        "observed_duration_over_180_minutes": extreme,
    }
    cases = {
        name: {
            "rows": int(mask.sum()),
            "model": eta_metrics(observed.to_numpy()[mask], predictions[mask])
            if mask.any()
            else None,
            "training_median_baseline": (
                eta_metrics(observed.to_numpy()[mask], np.full(int(mask.sum()), baseline_median))
                if mask.any()
                else None
            ),
        }
        for name, mask in case_masks.items()
    }
    errors = np.abs(observed.to_numpy() - predictions)
    return {
        "partition": {
            **partition_metadata,
            "counts": dict(
                zip(
                    ["train", "validation", "test"],
                    map(len, [train, validation, test]),
                    strict=True,
                )
            ),
            "source_row_index_sha256": {
                name: hashlib.sha256(
                    np.asarray(dataset.inputs.index[indices], dtype="<i8").tobytes()
                ).hexdigest()
                for name, indices in zip(
                    ["train", "validation", "test"], [train, validation, test], strict=True
                )
            },
        },
        "features": list(features.columns),
        "include_load": include_load,
        "load_availability_status": "unverified_optional_assumption"
        if include_load
        else "excluded",
        "validation_candidates": candidates,
        "selection_metric": "validation MAE minutes; ties retain first configuration",
        "selected_configuration": selected_configuration,
        "test": eta_metrics(observed, predictions),
        "baselines": {
            "training_mean": eta_metrics(observed, np.full(len(test), baseline_mean)),
            "training_median": eta_metrics(observed, np.full(len(test), baseline_median)),
        },
        "baseline_constants_minutes": {
            "training_mean": baseline_mean,
            "training_median": baseline_median,
        },
        "test_outcomes_over_180_minutes": int((observed > 180).sum()),
        "test_cases": cases,
        "case_interpretation": "Overlapping cases; duration cohorts use outcomes, not inputs.",
        "absolute_error_histogram": [
            {"interval": name, "rows": int(mask.sum())}
            for name, mask in [
                ("0_to_5_minutes_inclusive", errors <= 5),
                ("over_5_to_10_minutes", (errors > 5) & (errors <= 10)),
                ("over_10_to_20_minutes", (errors > 10) & (errors <= 20)),
                ("over_20_to_60_minutes", (errors > 20) & (errors <= 60)),
                ("over_60_minutes", errors > 60),
            ]
        ],
        "sampled_test_predictions": [
            {
                "observed_minutes": float(observed.iloc[i]),
                "predicted_minutes": float(predictions[i]),
            }
            for i in np.linspace(0, len(test) - 1, min(100, len(test)), dtype=int)
        ],
    }


def research_metadata(dataset):
    return {
        "schema_version": 1,
        "task": "separate ETA research benchmark, not delay classification",
        "source_audit": dataset.audit,
        "protocol": "Whole source-date 60/20/20 chronological split; unavailable outcomes purged",
        "model": "LightGBM regression_l1; 300 trees; learning rate 0.05; seed 42; two CPU threads",
        "library_versions": {
            name: version(name) for name in ["lightgbm", "pandas", "scikit-learn", "numpy"]
        },
        "serving_models_modified": False,
        "serving_promotion_approved": False,
        "warnings": [
            "Original business provenance, timezone and monetary units are unverified.",
            "No observed promised deadline; ETA errors are not delay-classification accuracy.",
            "All eligible positive durations retained, including extreme outcomes.",
            "Validation-only tuning; do not retune using results from the same test holdout.",
            "Old ETA scores are not directly comparable across different targets/domains.",
        ],
    }


def summarize_research_windows(windows):
    """Summarize repeated temporal windows without pretending overlapping tests are independent."""
    result = {}
    for include_load in [False, True]:
        selected = [window for window in windows if window["include_load"] == include_load]
        if not selected:
            continue
        errors = [window["test"]["mae_minutes"] for window in selected]
        result["load_snapshot_assumption" if include_load else "order_only"] = {
            "window_count": len(selected),
            "mean_window_mae_minutes": float(np.mean(errors)),
            "min_window_mae_minutes": min(errors),
            "max_window_mae_minutes": max(errors),
            "windows_beating_training_median_mae": sum(
                window["test"]["mae_minutes"]
                < window["baselines"]["training_median"]["mae_minutes"]
                for window in selected
            ),
        }
    return {
        "variants": result,
        "interpretation": "Unweighted summary; overlapping windows are not independent trials.",
        "promotion_decision": "Not promoted; source and operational compatibility need review.",
    }
