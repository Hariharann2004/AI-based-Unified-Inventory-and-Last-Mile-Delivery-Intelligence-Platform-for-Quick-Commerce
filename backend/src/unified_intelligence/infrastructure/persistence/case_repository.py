import hashlib
import json
import uuid

from unified_intelligence.infrastructure.persistence.workbench_store import (
    WorkbenchStore,
    encode,
    now,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
 case_id TEXT PRIMARY KEY, case_key TEXT UNIQUE NOT NULL, record_id TEXT NOT NULL,
 kind TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, evidence TEXT NOT NULL, drafts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_audit (
 audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
 case_id TEXT NOT NULL REFERENCES cases(case_id),
 occurred_at TEXT NOT NULL, actor TEXT NOT NULL, event TEXT NOT NULL, reason TEXT NOT NULL
);
"""


def action_drafts(evidence):
    if evidence["kind"] == "unified":
        return [
            draft
            for kind in ["inventory", "delivery"]
            for draft in action_drafts(
                {
                    "kind": kind,
                    "assessment": evidence["assessment"][kind],
                }
            )
        ]
    result, assessment = [], evidence["assessment"]
    if evidence["kind"] == "inventory" and assessment["reorder_required"]:
        quantity = assessment["recommended_reorder_quantity"]
        result.append(
            {
                "type": "replenishment" if quantity else "stock_risk_review",
                "quantity": quantity,
                "warehouse": assessment["warehouse_id"],
            }
        )
    if evidence["kind"] == "delivery" and assessment["delay_probability"] >= 0.35:
        result.append(
            {"type": "delivery_escalation", "eta_minutes": assessment["predicted_eta_minutes"]}
        )
    return [{**draft, "status": "pending", "external_execution": False} for draft in result]


class CaseRepository(WorkbenchStore):
    @staticmethod
    def ensure(connection):
        connection.executescript(SCHEMA)

    @staticmethod
    def decode(row):
        return {key: value for key, value in dict(row).items() if key != "case_key"} | {
            "evidence": json.loads(row["evidence"]),
            "drafts": json.loads(row["drafts"]),
        }

    def save_case(self, evidence):
        key = hashlib.sha256(
            encode(
                {
                    k: evidence[k]
                    for k in [
                        "record_id",
                        "inputs",
                        "models",
                        "provenance",
                    ]
                }
            ).encode()
        ).hexdigest()
        with self.connection() as connection:
            self.ensure(connection)
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT * FROM cases WHERE case_key=?", (key,)).fetchone()
            if existing:
                return self.decode(existing)
            case_id = str(uuid.uuid4())
            created = now()
            connection.execute(
                "INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    case_id,
                    key,
                    evidence["record_id"],
                    evidence["kind"],
                    evidence["decision"]["operational_priority"],
                    "open",
                    created,
                    encode(evidence),
                    encode(action_drafts(evidence)),
                ),
            )
            connection.execute(
                "INSERT INTO case_audit(case_id,occurred_at,actor,event,reason) VALUES (?,?,?,?,?)",
                (case_id, created, "system", "created", evidence["provenance"]),
            )
            row = connection.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        return self.decode(row)

    def cases(self, *, kind=None, status=None, offset=0, limit=50):
        clauses, parameters = [], []
        for column, value in [("kind", kind), ("status", status)]:
            if value:
                clauses.append(f"{column}=?")
                parameters.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connection() as connection:
            self.ensure(connection)
            total = connection.execute("SELECT count(*) FROM cases" + where, parameters).fetchone()[
                0
            ]
            rows = connection.execute(
                "SELECT * FROM cases"
                + where
                + " ORDER BY CASE priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 ELSE 2 END, "
                "created_at DESC LIMIT ? OFFSET ?",
                [*parameters, max(1, min(limit, 100)), max(0, offset)],
            ).fetchall()
        return {"total": total, "cases": [self.decode(row) for row in rows]}

    def case(self, case_id):
        with self.connection() as connection:
            self.ensure(connection)
            row = connection.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
            if row is None:
                raise KeyError("Case not found.")
            audit = connection.execute(
                "SELECT occurred_at,actor,event,reason FROM case_audit "
                "WHERE case_id=? ORDER BY audit_id",
                (case_id,),
            ).fetchall()
        return {**self.decode(row), "audit": [dict(event) for event in audit]}

    def transition(self, case_id, action, actor, reason):
        if action not in {"approved", "dismissed"}:
            raise ValueError("Action must be approved or dismissed.")
        if not actor.strip() or (action == "dismissed" and not reason.strip()):
            raise ValueError("Reviewer required; dismissals also require a reason.")
        with self.connection() as connection:
            self.ensure(connection)
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
            if row is None:
                raise KeyError("Case not found.")
            if row["status"] == action:
                return self.decode(row)
            if row["status"] != "open":
                raise ValueError("Case already reviewed; terminal decisions cannot be overwritten.")
            drafts = json.loads(row["drafts"])
            if action == "approved" and not drafts:
                raise ValueError("This case has no action draft to approve.")
            drafts = [{**draft, "status": action} for draft in drafts]
            connection.execute(
                "UPDATE cases SET status=?,drafts=? WHERE case_id=?",
                (
                    action,
                    encode(drafts),
                    case_id,
                ),
            )
            connection.execute(
                "INSERT INTO case_audit(case_id,occurred_at,actor,event,reason) VALUES (?,?,?,?,?)",
                (
                    case_id,
                    now(),
                    actor.strip(),
                    action,
                    reason.strip() or "Internal draft approved",
                ),
            )
        return self.case(case_id)
