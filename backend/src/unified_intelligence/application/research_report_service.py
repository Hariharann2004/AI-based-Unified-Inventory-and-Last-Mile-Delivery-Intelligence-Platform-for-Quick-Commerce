"""Read only the approved, server-owned ETA evidence snapshot."""

import json

from unified_intelligence.core.config import PROJECT_ROOT


class ResearchReportService:
    benchmark_id = "porter-eta-v1"

    def __init__(self, root=PROJECT_ROOT):
        self.root = root

    def get(self, benchmark_id):
        if benchmark_id != self.benchmark_id:
            raise KeyError("Research benchmark not found.")
        report = json.loads((self.root / "reports/porter_eta_benchmark.json").read_text())
        manifest = json.loads((self.root / "artifacts/delivery-benchmark-source.json").read_text())
        if (
            report.get("schema_version") != 1
            or report.get("source_audit", {}).get("csv_sha256") != manifest["csv_sha256"]
            or report.get("serving_models_modified") is not False
            or report.get("serving_promotion_approved") is not False
            or not report.get("windows")
        ):
            raise ValueError("Research evidence does not match the approved source contract.")
        return {"benchmark_id": self.benchmark_id, "report": report, "saved_evidence": True}

    def reports(self):
        if not (self.root / "reports/porter_eta_benchmark.json").is_file():
            return {"reports": [], "message": "Run the offline ETA benchmark CLI first."}
        self.get(self.benchmark_id)
        return {"reports": [{"benchmark_id": self.benchmark_id, "title": "Porter ETA benchmark"}]}
