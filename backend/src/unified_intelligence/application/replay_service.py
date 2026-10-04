import json
import uuid

from unified_intelligence.application.batch_service import identity
from unified_intelligence.infrastructure.persistence.workbench_store import encode, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS replays (
 run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL
);
"""


class ReplayConflict(ValueError):
    pass


class ReplayService:
    def __init__(self, store, batch):
        self.store, self.batch = store, batch

    def snapshot(self):
        return {p.name: identity(p)["sha256"] for p in self.batch.model_directory.glob("*.joblib")}

    def start(self, kind, import_id, limit):
        with self.store.connection() as connection:
            connection.executescript(SCHEMA)
            rows = connection.execute(
                "SELECT record_id FROM operational_records WHERE kind=? AND import_id=? "
                "ORDER BY occurred_at,position LIMIT ?",
                (kind, import_id, limit),
            ).fetchall()
            if not rows:
                raise ValueError("No records for this dataset import and kind.")
            run = {
                "run_id": str(uuid.uuid4()),
                "created_at": now(),
                "kind": kind,
                "import_id": import_id,
                "record_ids": [row["record_id"] for row in rows],
                "cursor": 0,
                "total": len(rows),
                "status": "ready",
                "events": [],
                "mode": "historical_replay",
                "accuracy_evaluation": False,
                "sequence_note": "Date then source row"
                if kind == "inventory"
                else "Source row order; no verified delivery timestamps",
                "model_snapshot": self.snapshot(),
            }
            connection.execute(
                "INSERT INTO replays VALUES (?,?,?)",
                (
                    run["run_id"],
                    run["created_at"],
                    encode(run),
                ),
            )
        return run

    def get(self, run_id):
        with self.store.connection() as connection:
            connection.executescript(SCHEMA)
            row = connection.execute(
                "SELECT payload FROM replays WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Replay not found.")
        return json.loads(row["payload"])

    def step(self, run_id, expected_cursor, count):
        run = self.get(run_id)
        if run["cursor"] != expected_cursor:
            raise ReplayConflict("Replay advanced already; reload its current cursor.")
        if run["cursor"] == run["total"]:
            return run
        if self.snapshot() != run["model_snapshot"]:
            raise ValueError("Model artifacts changed; start a new replay.")
        selected = run["record_ids"][run["cursor"] : run["cursor"] + count]
        for record_id in selected:
            try:
                evidence = self.batch.assess(self.store.record(record_id))
                evidence["provenance"] = "historical_replay:" + run_id
                case = self.store.save_case(evidence)
                event = {
                    "record_id": record_id,
                    "case_id": case["case_id"],
                    "priority": case["priority"],
                    "status": "processed",
                }
            except (ValueError, KeyError, FileNotFoundError) as error:
                event = {"record_id": record_id, "status": "failed", "error": str(error)}
            run["events"].append(event)
        run["cursor"] += len(selected)
        run["status"] = (
            "running"
            if run["cursor"] < run["total"]
            else (
                "completed_with_errors"
                if any(e["status"] == "failed" for e in run["events"])
                else "completed"
            )
        )
        with self.store.connection() as connection:
            changed = connection.execute(
                "UPDATE replays SET payload=? WHERE run_id=? "
                "AND json_extract(payload,'$.cursor')=?",
                (encode(run), run_id, expected_cursor),
            ).rowcount
            if changed != 1:
                raise ReplayConflict("Concurrent replay step; reload the current run.")
        return run
