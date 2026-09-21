"""Small, reusable LightGBM wrapper used by every prediction task.

Only LightGBM models are created here. Pandas one-hot encoding is used solely to
prepare mixed tabular columns consistently during training and inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor


Task = Literal["regression", "classification"]


@dataclass
class LightGBMArtifact:
    task: Task
    raw_features: list[str]
    encoded_features: list[str]
    model: object

    @staticmethod
    def _encode(frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        for column in frame.columns:
            if pd.api.types.is_datetime64_any_dtype(frame[column]):
                frame[column] = frame[column].astype("int64") // 10**9
        return pd.get_dummies(frame, dummy_na=True, dtype=float)

    @classmethod
    def train(
        cls, X: pd.DataFrame, y: pd.Series, task: Task, random_state: int = 42
    ) -> "LightGBMArtifact":
        encoded = cls._encode(X)
        if task == "regression":
            model = LGBMRegressor(
                objective="regression_l1", n_estimators=300, learning_rate=0.05,
                num_leaves=31, random_state=random_state, verbosity=-1,
            )
        else:
            model = LGBMClassifier(
                objective="binary", n_estimators=300, learning_rate=0.05,
                num_leaves=31, random_state=random_state, verbosity=-1,
            )
        model.fit(encoded, y)
        return cls(task, list(X.columns), list(encoded.columns), model)

    def prepare(self, records: pd.DataFrame) -> pd.DataFrame:
        missing = set(self.raw_features) - set(records.columns)
        if missing:
            raise ValueError(f"Missing required input fields: {', '.join(sorted(missing))}")
        encoded = self._encode(records[self.raw_features])
        return encoded.reindex(columns=self.encoded_features, fill_value=0)

    def predict(self, records: pd.DataFrame) -> np.ndarray:
        return self.model.predict(self.prepare(records))

    def predict_proba(self, records: pd.DataFrame) -> np.ndarray:
        if self.task != "classification":
            raise ValueError("Probabilities are only available for a classification model.")
        return self.model.predict_proba(self.prepare(records))[:, 1]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path: Path) -> "LightGBMArtifact":
        return joblib.load(path)
