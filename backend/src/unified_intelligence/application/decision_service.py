from typing import Any

from unified_intelligence.application.delivery_service import DeliveryService
from unified_intelligence.application.inventory_service import InventoryService
from unified_intelligence.domain.decisions import UnifiedDecisionPolicy


class DecisionService:
    def __init__(self, inventory_service: InventoryService, delivery_service: DeliveryService, policy: UnifiedDecisionPolicy | None = None) -> None:
        self.inventory_service = inventory_service
        self.delivery_service = delivery_service
        self.policy = policy or UnifiedDecisionPolicy()

    def evaluate(self, inventory_record: dict[str, Any], delivery_record: dict[str, Any] | None = None) -> dict[str, Any]:
        inventory = self.inventory_service.predict(inventory_record)
        delivery = self.delivery_service.predict(delivery_record) if delivery_record else None
        return {"inventory": inventory, "delivery": delivery, "decision": self.policy.evaluate(inventory, delivery).to_dict()}
