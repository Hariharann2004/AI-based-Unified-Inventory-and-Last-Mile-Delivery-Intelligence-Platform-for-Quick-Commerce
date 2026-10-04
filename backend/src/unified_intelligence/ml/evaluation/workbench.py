"""Fresh-model held-out evidence; never evaluates serving models on their training rows."""

from importlib.metadata import version

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.model_selection import GroupShuffleSplit

from unified_intelligence.ml.features.delivery import prepare_delivery_features
from unified_intelligence.ml.features.inventory import (
    derive_stockout_target,
    prepare_inventory_features,
)
from unified_intelligence.utils.modeling import LightGBMArtifact


def classification_evidence(y, probabilities, threshold):
    predicted = np.asarray(probabilities) >= threshold
    metrics = {
        "accuracy": float(accuracy_score(y, predicted)),
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "f1": float(f1_score(y, predicted, zero_division=0)),
        "brier_score": float(brier_score_loss(y, probabilities)),
        "roc_auc": float(roc_auc_score(y, probabilities)) if len(set(y)) > 1 else None,
        "average_precision": float(average_precision_score(y, probabilities)) if sum(y) else None,
    }
    precision, recall, _ = (
        precision_recall_curve(y, probabilities) if sum(y) else (np.array([]), np.array([]), None)
    )
    selected = np.linspace(0, len(precision) - 1, min(60, len(precision)), dtype=int)
    calibration = []
    probabilities = np.asarray(probabilities)
    y = np.asarray(y)
    bins = np.minimum((probabilities * 10).astype(int), 9)
    for bucket in range(10):
        mask = bins == bucket
        if mask.any():
            calibration.append(
                {
                    "predicted": float(probabilities[mask].mean()),
                    "observed": float(y[mask].mean()),
                    "count": int(mask.sum()),
                }
            )
    return {
        "metrics": metrics,
        "threshold": threshold,
        "confusion_matrix": confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
        "precision_recall": [
            {"precision": float(precision[i]), "recall": float(recall[i])} for i in selected
        ],
        "calibration": calibration,
    }


def regression_evidence(y, predicted):
    return {
        "mae": float(mean_absolute_error(y, predicted)),
        "rmse": float(root_mean_squared_error(y, predicted)),
    }


def date_windows(frame):
    dates = sorted(frame["Date"].unique())
    if len(dates) < 10:
        raise ValueError("Inventory evaluation requires at least 10 distinct dates.")
    windows = []
    for fraction in [0.6, 0.8, 1.0]:
        end = max(6, int(len(dates) * fraction))
        available = dates[:end]
        train_end, validation_end = int(end * 0.6), int(end * 0.8)
        windows.append(
            tuple(
                np.flatnonzero(frame["Date"].isin(period))
                for period in [
                    available[:train_end],
                    available[train_end:validation_end],
                    available[validation_end:],
                ]
            )
        )
    return windows


def delivery_windows(features):
    # Group identical feature vectors so duplicated examples cannot straddle partitions.
    groups = pd.util.hash_pandas_object(features, index=False)
    if groups.nunique() < 10:
        raise ValueError("Delivery evaluation requires at least 10 distinct feature groups.")
    windows = []
    for seed in [42, 43, 44]:
        train, remainder = next(
            GroupShuffleSplit(n_splits=1, test_size=0.4, random_state=seed).split(
                features, groups=groups
            )
        )
        validation, test = next(
            GroupShuffleSplit(n_splits=1, test_size=0.5, random_state=seed).split(
                features.iloc[remainder], groups=groups.iloc[remainder]
            )
        )
        windows.append((train, remainder[validation], remainder[test]))
    return windows


class WorkbenchEvaluator:
    def __init__(self, trainer=LightGBMArtifact.train):
        self.trainer = trainer

    def evaluate(self, records, kind):
        frame = pd.DataFrame([{**r["inputs"], **r["outcomes"]} for r in records])
        outcomes = pd.DataFrame([r["outcomes"] for r in records])
        regression_target = "Units_Sold" if kind == "inventory" else "delivery_time_minutes"
        if regression_target not in outcomes or (kind == "delivery" and "delayed" not in outcomes):
            raise ValueError("Evaluation requires observed target columns in the source CSV.")
        frame[regression_target] = outcomes[regression_target]
        if kind == "delivery":
            frame["delayed"] = outcomes["delayed"]
        numeric = pd.to_numeric(frame[regression_target], errors="coerce")
        valid = numeric.notna() & np.isfinite(numeric) & (numeric >= 0)
        if kind == "delivery":
            valid &= frame["delayed"].astype(str).str.lower().isin(["yes", "no"])
        rejected = int((~valid).sum())
        frame = frame.loc[valid].reset_index(drop=True)
        if len(frame) < 50:
            raise ValueError("Evaluation requires at least 50 records with valid observed targets.")
        y_reg = pd.to_numeric(frame[regression_target])
        if kind == "inventory":
            frame["Date"] = pd.to_datetime(frame["Date"])
            features = prepare_inventory_features(frame)
            frame["Units_Sold"] = y_reg
            y_class = derive_stockout_target(frame)
            windows = date_windows(frame)
            protocol = (
                "Three expanding date windows; 60/20/20 train/validation/test; dates kept whole"
            )
            warnings = [
                "Derived stockout label, not real stockout outcomes.",
                "Daily tabular demand prediction, not a multi-step time-series forecast.",
            ]
        else:
            features = prepare_delivery_features(frame).drop(columns=["delivery_rating"])
            y_class = frame["delayed"].astype(str).str.lower().eq("yes").astype(int)
            windows = delivery_windows(features)
            protocol = (
                "Three seeded grouped 60/20/20 splits; identical inputs grouped; "
                "no verified chronology"
            )
            warnings = [
                "delivery_rating excluded: pre-delivery availability unverified.",
                "No verified timestamps: this is not temporal delivery backtesting.",
            ]
        reports = []
        for index, (train, validation, test) in enumerate(windows):
            if y_class.iloc[train].nunique() != 2:
                raise ValueError(f"Window {index + 1} training target needs both risk classes.")
            regressor = self.trainer(features.iloc[train], y_reg.iloc[train], "regression")
            classifier = self.trainer(features.iloc[train], y_class.iloc[train], "classification")
            val_probability = classifier.predict_proba(features.iloc[validation])
            # Select only on validation; test outcomes never influence threshold choice.
            threshold = max(
                [0.35, 0.5, 0.7],
                key=lambda t: f1_score(
                    y_class.iloc[validation], val_probability >= t, zero_division=0
                ),
            )
            predicted = regressor.predict(features.iloc[test])
            probabilities = classifier.predict_proba(features.iloc[test])
            samples = np.linspace(0, len(test) - 1, min(100, len(test)), dtype=int)
            segments = []
            segment_column = "Warehouse_ID" if kind == "inventory" else "Traffic_Level"
            for segment, subset in frame.iloc[test].groupby(segment_column):
                positions = np.flatnonzero(frame.iloc[test][segment_column].to_numpy() == segment)
                segments.append(
                    {
                        "segment": str(segment),
                        "count": len(subset),
                        **regression_evidence(
                            y_reg.iloc[test].iloc[positions], predicted[positions]
                        ),
                    }
                )
            reports.append(
                {
                    "window": index + 1,
                    "counts": {
                        "train": len(train),
                        "validation": len(validation),
                        "test": len(test),
                    },
                    "regression": regression_evidence(y_reg.iloc[test], predicted),
                    "constant_baseline": regression_evidence(
                        y_reg.iloc[test], np.full(len(test), y_reg.iloc[train].mean())
                    ),
                    "classification": classification_evidence(
                        y_class.iloc[test], probabilities, threshold
                    ),
                    "action_threshold": classification_evidence(
                        y_class.iloc[test], probabilities, 0.7
                    ),
                    "validation_f1": float(
                        f1_score(
                            y_class.iloc[validation], val_probability >= threshold, zero_division=0
                        )
                    ),
                    "samples": [
                        {
                            "actual": float(y_reg.iloc[test[i]]),
                            "predicted": float(predicted[i]),
                            "position": int(test[i]),
                            "date": str(frame.iloc[test[i]].get("Date", "")),
                        }
                        for i in samples
                    ],
                    "segments": segments,
                }
            )
        return {
            "algorithm": "LightGBM only",
            "library_versions": {
                name: version(name) for name in ["lightgbm", "pandas", "scikit-learn"]
            },
            "kind": kind,
            "protocol": protocol,
            "accepted_targets": len(frame),
            "rejected_targets": rejected,
            "warnings": warnings,
            "serving_models_modified": False,
            "features": list(features.columns),
            "windows": reports,
            "note": "Temporary evaluation models are freshly trained and not promoted to serving.",
        }
