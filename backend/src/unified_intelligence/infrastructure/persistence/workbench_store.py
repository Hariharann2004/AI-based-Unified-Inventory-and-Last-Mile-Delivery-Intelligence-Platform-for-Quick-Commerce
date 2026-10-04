"""Transactional storage with explicit independent-dataset provenance."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS imports (
 import_id TEXT PRIMARY KEY, kind TEXT NOT NULL, source TEXT NOT NULL,
 fingerprint TEXT NOT NULL, created_at TEXT NOT NULL, summary TEXT NOT NULL,
 UNIQUE(kind, fingerprint)
);
CREATE TABLE IF NOT EXISTS operational_records (
 record_id TEXT PRIMARY KEY, import_id TEXT NOT NULL REFERENCES imports(import_id),
 kind TEXT NOT NULL, position INTEGER NOT NULL, occurred_at TEXT,
 inputs TEXT NOT NULL, outcomes TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS records_position ON operational_records(kind, import_id, position);
"""


def encode(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def now():
    return datetime.now(UTC).isoformat()


class WorkbenchStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA)
            with connection:
                yield connection
        finally:
            connection.close()

    def save_import(self, metadata, records):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT summary FROM imports WHERE kind=? AND fingerprint=?",
                (metadata["kind"], metadata["fingerprint"]),
            ).fetchone()
            if existing:
                return {**json.loads(existing["summary"]), "duplicate": True}
            connection.execute(
                "INSERT INTO imports VALUES (?,?,?,?,?,?)",
                (
                    metadata["import_id"],
                    metadata["kind"],
                    metadata["source"],
                    metadata["fingerprint"],
                    metadata["created_at"],
                    encode(metadata),
                ),
            )
            connection.executemany(
                "INSERT INTO operational_records VALUES (?,?,?,?,?,?,?)",
                [
                    (
                        r["record_id"],
                        metadata["import_id"],
                        metadata["kind"],
                        r["position"],
                        r.get("occurred_at"),
                        encode(r["inputs"]),
                        encode(r["outcomes"]),
                    )
                    for r in records
                ],
            )
        return {**metadata, "duplicate": False}

    def imports(self):
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT summary FROM imports ORDER BY created_at DESC"
            ).fetchall()
        return [json.loads(row["summary"]) for row in rows]

    @staticmethod
    def decode_record(row):
        return {
            **dict(row),
            "inputs": json.loads(row["inputs"]),
            "outcomes": json.loads(row["outcomes"]),
        }

    def records(self, kind, *, import_id=None, limit=50, offset=0, warehouse=None, sku=None):
        where, parameters = "kind=?", [kind]
        if import_id:
            where += " AND import_id=?"
            parameters.append(import_id)
        for field, value in [("Warehouse_ID", warehouse), ("SKU_ID", sku)]:
            if value:
                where += " AND json_extract(inputs, ?) = ?"
                parameters.extend(["$." + field, value])
        with self.connection() as connection:
            count = connection.execute(
                f"SELECT count(*) FROM operational_records WHERE {where}",
                parameters,
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM operational_records WHERE {where} "
                "ORDER BY import_id, position LIMIT ? OFFSET ?",
                [*parameters, max(1, min(limit, 100)), max(0, offset)],
            ).fetchall()
        return {"total": count, "records": [self.decode_record(row) for row in rows]}

    def record(self, record_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM operational_records WHERE record_id=?",
                (record_id,),
            ).fetchone()
        if row is None:
            raise KeyError("Stored record not found.")
        return self.decode_record(row)
