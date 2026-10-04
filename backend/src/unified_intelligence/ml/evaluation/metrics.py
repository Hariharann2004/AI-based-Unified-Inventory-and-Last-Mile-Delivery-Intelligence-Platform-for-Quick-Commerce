import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, mean_absolute_error, mean_squared_error, roc_auc_score


def regression_metrics(y_true: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": round(float(mean_absolute_error(y_true, predicted)), 4),
        "rmse": round(float(mean_squared_error(y_true, predicted) ** 0.5), 4),
    }


def classification_metrics(y_true: pd.Series, probability: np.ndarray) -> dict[str, float]:
    result = {"accuracy": round(float(accuracy_score(y_true, probability >= 0.5)), 4)}
    if y_true.nunique() == 2:
        result["roc_auc"] = round(float(roc_auc_score(y_true, probability)), 4)
    return result
