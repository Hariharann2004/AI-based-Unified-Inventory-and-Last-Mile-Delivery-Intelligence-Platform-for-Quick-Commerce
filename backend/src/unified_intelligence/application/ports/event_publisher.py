from typing import Any, Protocol


class DecisionEventPublisher(Protocol):
    def publish(self, decision_id: str, outcome: dict[str, Any]) -> None: ...
