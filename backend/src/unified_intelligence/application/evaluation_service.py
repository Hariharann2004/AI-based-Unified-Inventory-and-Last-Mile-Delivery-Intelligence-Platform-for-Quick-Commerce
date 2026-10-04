"""Bounded local background evaluation, persisted reports, no model promotion."""

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from unified_intelligence.infrastructure.persistence.workbench_store import encode, now
from unified_intelligence.ml.evaluation.workbench import WorkbenchEvaluator

EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="uid-evaluation")
ADMISSION = threading.BoundedSemaphore(1)
SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluations (
 evaluation_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL
);
"""


class EvaluationService:
    def __init__(self, store, evaluator=None):
        self.store = store
        self.evaluator = evaluator or WorkbenchEvaluator()

    def save(self, report):
        with self.store.connection() as connection:
            connection.executescript(SCHEMA)
            connection.execute(
                "INSERT OR REPLACE INTO evaluations VALUES (?,?,?)",
                (
                    report["evaluation_id"],
                    report["created_at"],
                    encode(report),
                ),
            )

    def reports(self):
        with self.store.connection() as connection:
            connection.executescript(SCHEMA)
            rows = connection.execute(
                "SELECT payload FROM evaluations ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def get(self, evaluation_id):
        with self.store.connection() as connection:
            connection.executescript(SCHEMA)
            row = connection.execute(
                "SELECT payload FROM evaluations WHERE evaluation_id=?", (evaluation_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Evaluation report not found.")
        return json.loads(row["payload"])

    def execute(self, report):
        try:
            with self.store.connection() as connection:
                rows = connection.execute(
                    "SELECT * FROM operational_records WHERE kind=? AND import_id=? "
                    "ORDER BY position",
                    (report["kind"], report["import_id"]),
                ).fetchall()
            result = self.evaluator.evaluate(
                [self.store.decode_record(row) for row in rows], report["kind"]
            )
            report = {**report, "status": "completed", "completed_at": now(), "report": result}
        except Exception as error:
            report = {
                **report,
                "status": "failed",
                "completed_at": now(),
                "error": f"{type(error).__name__}: {error}",
            }
        self.save(report)
        return report

    def start(self, kind, import_id):
        imported = next(
            (i for i in self.store.imports() if i["import_id"] == import_id and i["kind"] == kind),
            None,
        )
        if not imported:
            raise ValueError("Select a matching dataset import first.")
        if not ADMISSION.acquire(blocking=False):
            raise ValueError("An evaluation is already running in this process. Try again later.")
        report = {
            "evaluation_id": str(uuid.uuid4()),
            "created_at": now(),
            "status": "running",
            "kind": kind,
            "import_id": import_id,
            "data_fingerprint": imported["fingerprint"],
        }
        try:
            self.save(report)
            future = EXECUTOR.submit(self.execute, report)
            future.add_done_callback(lambda _future: ADMISSION.release())
        except Exception:
            ADMISSION.release()
            raise
        return report
