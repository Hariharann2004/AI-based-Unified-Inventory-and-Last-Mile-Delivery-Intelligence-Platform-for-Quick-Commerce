from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class StoredDecision:
    decision_id: str
    created_at: str
    inventory_input: dict[str, Any]
    delivery_input: dict[str, Any] | None
    outcome: dict[str, Any]


class DecisionRepository(Protocol):
    def save(
        self,
        inventory_input: dict[str, Any],
        delivery_input: dict[str, Any] | None,
        outcome: dict[str, Any],
    ) -> StoredDecision: ...

    def list_recent(self, limit: int = 20) -> list[StoredDecision]: ...
