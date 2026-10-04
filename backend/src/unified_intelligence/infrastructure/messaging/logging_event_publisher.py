import logging
from typing import Any


class LoggingDecisionEventPublisher:
    """Local adapter that can be replaced by a queue or workflow integration."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def publish(self, decision_id: str, outcome: dict[str, Any]) -> None:
        self.logger.info(
            "decision_evaluated",
            extra={
                "decision_id": decision_id,
                "operational_priority": outcome["decision"]["operational_priority"],
            },
        )
