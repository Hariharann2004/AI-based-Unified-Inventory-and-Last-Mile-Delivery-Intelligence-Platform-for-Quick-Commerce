"""Durable per-record checkpoints with a single active local worker lease."""

import json
import sqlite3
import time
import uuid

from unified_intelligence.infrastructure.persistence.workbench_store import (
    WorkbenchStore,
    encode,
    now,
)

LEASE_SECONDS = 120
ACTIVE = ("queued", "running", "cancelling")
SCHEMA = """
CREATE TABLE IF NOT EXISTS processing_jobs (
 job_id TEXT PRIMARY KEY, kind TEXT NOT NULL, import_id TEXT NOT NULL,
 data_fingerprint TEXT NOT NULL, models TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, owner TEXT,
 lease_until REAL NOT NULL DEFAULT 0, error TEXT, revision INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_processing_job
 ON processing_jobs((1)) WHERE status IN ('queued','running','cancelling');
CREATE TABLE IF NOT EXISTS processing_items (
 job_id TEXT NOT NULL REFERENCES processing_jobs(job_id),
 record_id TEXT NOT NULL REFERENCES operational_records(record_id),
 position INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0, case_id TEXT, error TEXT,
 PRIMARY KEY(job_id,record_id)
);
CREATE INDEX IF NOT EXISTS processing_item_status ON processing_items(job_id,status,position);
"""


class ProcessingConflict(ValueError):
    pass


class ProcessingRepository(WorkbenchStore):
    def __init__(self, path, *, clock=time.time):
        super().__init__(path)
        self.clock = clock

    @staticmethod
    def ensure(connection):
        connection.executescript(SCHEMA)

    def recover(self, connection):
        connection.execute(
            "UPDATE processing_jobs SET status='interrupted',owner=NULL,lease_until=0,"
            "error=?,updated_at=?,revision=revision+1 "
            "WHERE status IN ('queued','running','cancelling') AND lease_until < ?",
            ("Worker lease expired. Resume remaining records explicitly.", now(), self.clock()),
        )

    def create(self, imported, models, owner):
        with self.connection() as connection:
            self.ensure(connection)
            connection.execute("BEGIN IMMEDIATE")
            self.recover(connection)
            active = connection.execute(
                "SELECT * FROM processing_jobs WHERE status IN ('queued','running','cancelling')"
            ).fetchone()
            if active:
                raise ProcessingConflict(
                    "Another full-import job is active. Wait or cancel it first."
                )
            job_id, timestamp = str(uuid.uuid4()), now()
            connection.execute(
                "INSERT INTO processing_jobs(job_id,kind,import_id,data_fingerprint,models,status,"
                "created_at,updated_at,owner,lease_until) VALUES (?,?,?,?,?,'queued',?,?,?,?)",
                (
                    job_id,
                    imported["kind"],
                    imported["import_id"],
                    imported["fingerprint"],
                    encode(models),
                    timestamp,
                    timestamp,
                    owner,
                    self.clock() + LEASE_SECONDS,
                ),
            )
            connection.execute(
                "INSERT INTO processing_items(job_id,record_id,position) "
                "SELECT ?,record_id,position FROM operational_records WHERE kind=? AND import_id=?",
                (job_id, imported["kind"], imported["import_id"]),
            )
            total = connection.execute(
                "SELECT count(*) FROM processing_items WHERE job_id=?", (job_id,)
            ).fetchone()[0]
            if not total:
                raise ValueError("The selected import has no accepted records to process.")
        return self.get(job_id)

    def get(self, job_id):
        with self.connection() as connection:
            self.ensure(connection)
            self.recover(connection)
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Processing job not found.")
            counts = dict(
                connection.execute(
                    "SELECT status,count(*) FROM processing_items WHERE job_id=? GROUP BY status",
                    (job_id,),
                ).fetchall()
            )
        result = {
            key: value for key, value in dict(row).items() if key not in {"owner", "lease_until"}
        }
        result["models"] = json.loads(result["models"])
        succeeded, failed = counts.get("succeeded", 0), counts.get("failed", 0)
        total = sum(counts.values())
        return {
            **result,
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "pending": counts.get("pending", 0),
            "processed": succeeded + failed,
            "progress_percent": round(100 * (succeeded + failed) / total, 2) if total else 0,
            "mode": "historical_full_import",
            "external_execution": False,
        }

    def jobs(self, import_id=None):
        with self.connection() as connection:
            self.ensure(connection)
            self.recover(connection)
            rows = connection.execute(
                "SELECT job_id FROM processing_jobs "
                + ("WHERE import_id=? " if import_id else "")
                + "ORDER BY created_at DESC LIMIT 20",
                [import_id] if import_id else [],
            ).fetchall()
        return [self.get(row["job_id"]) for row in rows]

    def items(self, job_id, *, status=None, limit=20, offset=0):
        self.get(job_id)
        if status not in {None, "pending", "succeeded", "failed"}:
            raise ValueError("Unknown processing item status.")
        with self.connection() as connection:
            where = "job_id=?" + (" AND status=?" if status else "")
            parameters = [job_id, status] if status else [job_id]
            total = connection.execute(
                f"SELECT count(*) FROM processing_items WHERE {where}", parameters
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT record_id,position,status,attempts,case_id,error FROM processing_items "
                f"WHERE {where} ORDER BY position LIMIT ? OFFSET ?",
                [*parameters, max(1, min(limit, 100)), max(0, offset)],
            ).fetchall()
        return {"total": total, "items": [dict(row) for row in rows]}

    def cancel(self, job_id):
        self.get(job_id)
        with self.connection() as connection:
            connection.execute(
                "UPDATE processing_jobs SET status='cancelling',updated_at=?,revision=revision+1 "
                "WHERE job_id=? AND status IN ('queued','running')",
                (now(), job_id),
            )
        return self.get(job_id)

    def resume(self, job_id, imported, models, owner, *, retry_failed=False):
        with self.connection() as connection:
            self.ensure(connection)
            connection.execute("BEGIN IMMEDIATE")
            self.recover(connection)
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Processing job not found.")
            if row["status"] not in {"cancelled", "interrupted", "failed", "completed_with_errors"}:
                raise ProcessingConflict("This job cannot be resumed in its current state.")
            if (
                row["data_fingerprint"] != imported["fingerprint"]
                or json.loads(row["models"]) != models
            ):
                raise ProcessingConflict(
                    "Source/model version changed; resume requires the original versions."
                )
            if retry_failed:
                connection.execute(
                    "UPDATE processing_items SET status='pending',error=NULL "
                    "WHERE job_id=? AND status='failed'",
                    (job_id,),
                )
            pending = connection.execute(
                "SELECT count(*) FROM processing_items WHERE job_id=? AND status='pending'",
                (job_id,),
            ).fetchone()[0]
            if not pending:
                raise ProcessingConflict(
                    "No remaining records. Choose retry failed records if applicable."
                )
            try:
                connection.execute(
                    "UPDATE processing_jobs SET status='queued',owner=?,lease_until=?,error=NULL,"
                    "updated_at=?,revision=revision+1 WHERE job_id=?",
                    (owner, self.clock() + LEASE_SECONDS, now(), job_id),
                )
            except sqlite3.IntegrityError as error:
                raise ProcessingConflict("Another full-import job is active.") from error
        return self.get(job_id)

    def heartbeat(self, job_id, owner):
        with self.connection() as connection:
            changed = connection.execute(
                "UPDATE processing_jobs SET status=CASE "
                "WHEN status='queued' THEN 'running' ELSE status END,"
                "lease_until=?,updated_at=? WHERE job_id=? AND owner=? AND lease_until >= ? "
                "AND status IN ('queued','running')",
                (self.clock() + LEASE_SECONDS, now(), job_id, owner, self.clock()),
            ).rowcount
        return bool(changed)

    def pending_records(self, job_id, limit=25):
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT r.* FROM operational_records r JOIN processing_items i USING(record_id) "
                "WHERE i.job_id=? AND i.status='pending' ORDER BY i.position LIMIT ?",
                (job_id, max(1, min(limit, 100))),
            ).fetchall()
        return [self.decode_record(row) for row in rows]

    def checkpoint(self, job_id, owner, record_id, *, case_id=None, error=None):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            owned = connection.execute(
                "SELECT 1 FROM processing_jobs WHERE job_id=? AND owner=? AND lease_until>=? "
                "AND status IN ('running','cancelling')",
                (job_id, owner, self.clock()),
            ).fetchone()
            if not owned:
                raise ProcessingConflict("Worker lease was lost; checkpoint rejected.")
            connection.execute(
                "UPDATE processing_items SET status=?,attempts=attempts+1,case_id=?,error=? "
                "WHERE job_id=? AND record_id=? AND status='pending'",
                ("failed" if error else "succeeded", case_id, error, job_id, record_id),
            )
            connection.execute(
                "UPDATE processing_jobs SET updated_at=?,lease_until=?,revision=revision+1 "
                "WHERE job_id=?",
                (now(), self.clock() + LEASE_SECONDS, job_id),
            )

    def finish(self, job_id, owner, status, error=None):
        with self.connection() as connection:
            connection.execute(
                "UPDATE processing_jobs SET status=?,error=?,owner=NULL,lease_until=0,"
                "updated_at=?,revision=revision+1 WHERE job_id=? AND owner=? "
                "AND status IN ('queued','running','cancelling')",
                (status, error, now(), job_id, owner),
            )
