from pathlib import Path
from typing import Any

import pandas as pd

from unified_intelligence.core.config import Settings, get_settings
from unified_intelligence.domain.delivery import DeliveryPolicy
from unified_intelligence.utils.modeling import LightGBMArtifact


class DeliveryService:
    def __init__(
        self,
        eta_model: Any | None = None,
        delay_model: Any | None = None,
        *,
        settings: Settings | None = None,
        eta_path: Path | None = None,
        delay_path: Path | None = None,
        policy: DeliveryPolicy | None = None,
    ) -> None:
        config = settings or get_settings()
        self.eta_model = eta_model or LightGBMArtifact.load(
            eta_path or config.model_directory / "delivery_eta.joblib"
        )
        self.delay_model = delay_model or LightGBMArtifact.load(
            delay_path or config.model_directory / "delivery_delay.joblib"
        )
        self.policy = policy or DeliveryPolicy()

    def predict(self, record: dict[str, Any]) -> dict[str, Any]:
        frame = pd.DataFrame([record])
        eta = float(self.eta_model.predict(frame)[0])
        probability = float(self.delay_model.predict_proba(frame)[0])
        return self.policy.evaluate(record, eta, probability).to_dict()
