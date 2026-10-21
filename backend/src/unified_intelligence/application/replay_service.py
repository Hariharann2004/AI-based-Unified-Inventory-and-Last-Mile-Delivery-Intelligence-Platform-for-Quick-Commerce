import json
import uuid
from datetime import date

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

    def start(self, kind, import_id, limit, *, start_date=None, end_date=None):
        start_date = date.fromisoformat(str(start_date)) if start_date else None
        end_date = date.fromisoformat(str(end_date)) if end_date else None
        if (start_date or end_date) and kind != "inventory":
            raise ValueError("Date ranges require inventory records with recorded dates.")
        if start_date and end_date and start_date > end_date:
            raise ValueError("Start date must be on or before end date.")
        where, parameters = "kind=? AND import_id=?", [kind, import_id]
        for value, operator in [(start_date, ">="), (end_date, "<=")]:
            if value:
                where += f" AND substr(occurred_at,1,10) {operator} ?"
                parameters.append(value.isoformat())
        with self.store.connection() as connection:
            connection.executescript(SCHEMA)
            eligible = connection.execute(
                "SELECT count(*) FROM operational_records WHERE " + where, parameters
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT record_id,occurred_at FROM operational_records WHERE "
                + where
                + " ORDER BY occurred_at,position LIMIT ?",
                [*parameters, limit],
            ).fetchall()
            if not rows:
                raise ValueError(
                    "No records for this dataset import, kind and selected date range."
                )
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
                "date_range": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "selected_dates": {
                    "first": rows[0]["occurred_at"],
                    "last": rows[-1]["occurred_at"],
                },
                "eligible_records": eligible,
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
                record = self.store.record(record_id)
                evidence = self.batch.assess(record)
                evidence["provenance"] = "historical_replay:" + run_id
                case = self.store.save_case(evidence)
                event = {
                    "record_id": record_id,
                    "case_id": case["case_id"],
                    "priority": case["priority"],
                    "status": "processed",
                    "occurred_at": record.get("occurred_at"),
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
