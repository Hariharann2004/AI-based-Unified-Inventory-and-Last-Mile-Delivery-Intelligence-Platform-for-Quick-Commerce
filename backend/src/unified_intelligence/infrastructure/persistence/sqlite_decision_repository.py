from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from unified_intelligence.application.ports import StoredDecision

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    inventory_input TEXT NOT NULL,
    delivery_input TEXT,
    outcome TEXT NOT NULL
)
"""


class SQLiteDecisionRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @classmethod
    def from_url(cls, database_url: str, project_root: Path) -> SQLiteDecisionRepository:
        prefix = "sqlite:///"
        if not database_url.startswith(prefix):
            raise ValueError("Only sqlite:/// database URLs are supported by this adapter.")
        raw_path = database_url.removeprefix(prefix)
        database_path = Path(raw_path)
        if not database_path.is_absolute():
            database_path = project_root / database_path
        return cls(database_path.resolve())

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(SCHEMA)
        return connection

    @staticmethod
    def _encode(value: dict[str, Any] | None) -> str | None:
        return (
            json.dumps(value, separators=(",", ":"), sort_keys=True) if value is not None else None
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> StoredDecision:
        return StoredDecision(
            decision_id=row["decision_id"],
            created_at=row["created_at"],
            inventory_input=json.loads(row["inventory_input"]),
            delivery_input=json.loads(row["delivery_input"]) if row["delivery_input"] else None,
            outcome=json.loads(row["outcome"]),
        )

    def save(
        self,
        inventory_input: dict[str, Any],
        delivery_input: dict[str, Any] | None,
        outcome: dict[str, Any],
    ) -> StoredDecision:
        record = StoredDecision(
            decision_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC).isoformat(),
            inventory_input=inventory_input,
            delivery_input=delivery_input,
            outcome=outcome,
        )
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO decisions (
                        decision_id, created_at, inventory_input, delivery_input, outcome
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.decision_id,
                        record.created_at,
                        self._encode(record.inventory_input),
                        self._encode(record.delivery_input),
                        self._encode(record.outcome),
                    ),
                )
        return record

    def list_recent(self, limit: int = 20) -> list[StoredDecision]:
        safe_limit = max(1, min(limit, 100))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (safe_limit,)
            ).fetchall()
        return [self._decode(row) for row in rows]
