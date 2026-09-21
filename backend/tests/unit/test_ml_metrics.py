import numpy as np
import pandas as pd

from unified_intelligence.ml.evaluation import classification_metrics, regression_metrics


def test_regression_metrics_report_mae_and_rmse() -> None:
    result = regression_metrics(pd.Series([1.0, 3.0]), np.array([2.0, 3.0]))

    assert result == {"mae": 0.5, "rmse": 0.7071}


def test_classification_metrics_include_auc_for_binary_target() -> None:
    result = classification_metrics(pd.Series([0, 1]), np.array([0.2, 0.8]))

    assert result == {"accuracy": 1.0, "roc_auc": 1.0}
