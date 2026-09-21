from typing import Any

from unified_intelligence.application.delivery_service import DeliveryService
from unified_intelligence.application.inventory_service import InventoryService
from unified_intelligence.application.ports import DecisionEventPublisher, DecisionRepository
from unified_intelligence.domain.decisions import UnifiedDecisionPolicy


class DecisionService:
    def __init__(
        self,
        inventory_service: InventoryService,
        delivery_service: DeliveryService,
        policy: UnifiedDecisionPolicy | None = None,
        repository: DecisionRepository | None = None,
        event_publisher: DecisionEventPublisher | None = None,
    ) -> None:
        self.inventory_service = inventory_service
        self.delivery_service = delivery_service
        self.policy = policy or UnifiedDecisionPolicy()
        self.repository = repository
        self.event_publisher = event_publisher

    def evaluate(
        self, inventory_record: dict[str, Any], delivery_record: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        inventory = self.inventory_service.predict(inventory_record)
        delivery = self.delivery_service.predict(delivery_record) if delivery_record else None
        outcome = {
            "inventory": inventory,
            "delivery": delivery,
            "decision": self.policy.evaluate(inventory, delivery).to_dict(),
        }
        if self.repository is not None:
            record = self.repository.save(inventory_record, delivery_record, outcome)
            outcome["decision_id"] = record.decision_id
            if self.event_publisher is not None:
                self.event_publisher.publish(record.decision_id, outcome)
        return outcome
