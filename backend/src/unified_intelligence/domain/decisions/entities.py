from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class UnifiedDecision:
    operational_priority: str
    assigned_warehouse_only: bool
    actions: list[str]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
