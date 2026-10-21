"""Select saved historical assessments for demonstration, never invent model outcomes."""

from collections import defaultdict

PRIORITIES = ("Critical", "High", "Normal")


def spread_across_dates(rows, limit):
    """Prefer evenly spread distinct source dates; then fill from remaining records."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["occurred_at"] or "")[:10]].append(row)
    dates = sorted(groups)
    if not dates:
        return []
    count = min(limit, len(dates))
    indices = [0] if count == 1 else [i * (len(dates) - 1) // (count - 1) for i in range(count)]
    selected = [groups[dates[index]][0] for index in indices]
    selected_ids = {row["record_id"] for row in selected}
    for row in rows:
        if len(selected) >= limit:
            break
        if row["record_id"] not in selected_ids:
            selected.append(row)
            selected_ids.add(row["record_id"])
    return sorted(selected, key=lambda row: (row["occurred_at"] or "", row["position"]))


class ReplayDemonstrationService:
    def __init__(self, store):
        self.store = store

    def select(self, kind, import_id, per_priority=3):
        if kind not in {"inventory", "delivery"} or not 1 <= per_priority <= 10:
            raise ValueError("Select inventory/delivery and 1–10 saved cases per priority.")
        with self.store.connection() as connection:
            source = connection.execute(
                "SELECT source FROM imports WHERE import_id=? AND kind=?", (import_id, kind)
            ).fetchone()
            if source is None:
                raise ValueError("No matching dataset import for the selected record type.")
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cases'"
            ).fetchone()
            rows = (
                []
                if not exists
                else connection.execute(
                    """
                WITH historical AS (
                  SELECT c.case_id,c.record_id,c.priority,c.created_at,
                    r.occurred_at,r.position,
                    json_extract(r.inputs,'$.SKU_ID') AS sku_id,
                    json_extract(r.inputs,'$.Warehouse_ID') AS warehouse_id,
                    json_extract(r.inputs,'$.delivery_id') AS delivery_id,
                    row_number() OVER (
                      PARTITION BY c.record_id ORDER BY c.created_at DESC,c.case_id
                    ) AS assessment_rank
                  FROM cases c JOIN operational_records r ON r.record_id=c.record_id
                  WHERE c.kind=? AND r.kind=? AND r.import_id=?
                    AND json_extract(c.evidence,'$.provenance')='historical_dataset'
                    AND json_extract(c.evidence,'$.kind')=c.kind
                    AND json_extract(c.evidence,'$.import_id')=r.import_id
                    AND json_extract(c.evidence,'$.inputs')=r.inputs
                    AND json_extract(c.evidence,'$.decision.operational_priority')=c.priority
                )
                SELECT * FROM historical WHERE assessment_rank=1
                ORDER BY occurred_at,position,case_id
                """,
                    (kind, kind, import_id),
                ).fetchall()
            )
        groups = {priority: [] for priority in PRIORITIES}
        for row in rows:
            if row["priority"] in groups:
                groups[row["priority"]].append(dict(row))
        events = []
        for candidates in groups.values():
            for item in spread_across_dates(candidates, per_priority):
                events.append(
                    {
                        "record_id": item["record_id"],
                        "case_id": item["case_id"],
                        "priority": item["priority"],
                        "status": "processed",
                        "occurred_at": item["occurred_at"],
                        "source_position": item["position"],
                        "sku_id": item["sku_id"],
                        "warehouse_id": item["warehouse_id"],
                        "delivery_id": item["delivery_id"],
                        "assessment_saved_at": item["created_at"],
                        "provenance": "historical_dataset",
                    }
                )
        return {
            "mode": "selected_demonstration",
            "kind": kind,
            "import_id": import_id,
            "source": source["source"],
            "per_priority": per_priority,
            "accuracy_evaluation": False,
            "representative_sample": False,
            "new_predictions": False,
            "selection_note": (
                "Deliberately selected saved historical assessments, not a representative "
                "sample, chronological replay or accuracy evaluation. Original model outputs "
                "are unchanged; model identity and evidence remain in each linked case."
            ),
            "available_counts": {priority: len(items) for priority, items in groups.items()},
            "selected_counts": {
                priority: sum(event["priority"] == priority for event in events)
                for priority in PRIORITIES
            },
            "missing_priorities": [priority for priority, items in groups.items() if not items],
            "events": events,
        }
