import hashlib
import importlib
import json

import pytest
from test_batches import Stub
from test_evaluation import observed_records

from unified_intelligence.application.evaluation_service import EvaluationService
from unified_intelligence.application.evidence_export import ExportConflict, export_evidence, plot
from unified_intelligence.application.research_report_service import ResearchReportService
from unified_intelligence.infrastructure.persistence.case_repository import CaseRepository
from unified_intelligence.ml.evaluation.workbench import WorkbenchEvaluator


@pytest.fixture()
def completed():
    return {
        "evaluation_id": "safe-id",
        "status": "completed",
        "kind": "inventory",
        "created_at": "2024-01-01",
        "data_fingerprint": "fixture-source-sha",
        "worker_id": "private-worker",
        "report": WorkbenchEvaluator(lambda *_: Stub()).evaluate(
            observed_records("inventory"), "inventory"
        ),
    }


def test_json_export_hash_provenance_and_no_private_worker(completed):
    content, filename = export_evidence(completed, "operational", "json")
    result = json.loads(content)
    assert filename == "operational-safe-id.json"
    assert result["report"] == completed["report"]
    assert result["provenance"]["data_fingerprint"] == "fixture-source-sha"
    assert "worker_id" not in result["provenance"]
    canonical = json.dumps(completed["report"], sort_keys=True, ensure_ascii=False, allow_nan=False)
    assert result["report_sha256"] == hashlib.sha256(canonical.encode()).hexdigest()
    assert result["exported_at"].endswith("+00:00")


@pytest.mark.parametrize("kind", ["inventory", "delivery"])
def test_html_all_windows_tables_charts_and_escaped_strings(completed, kind):
    completed["report"] = WorkbenchEvaluator(lambda *_: Stub()).evaluate(
        observed_records(kind), kind
    )
    completed["report"]["warnings"].append("<script>alert('x')</script>")
    completed["report"]["protocol"] = '<img src=x onerror="bad()">'
    completed["report"]["windows"][0]["segments"][0]["segment"] = "<iframe>"
    content, filename = export_evidence(completed, "operational", "html")
    assert filename.endswith(".html")
    assert "<script>" not in content and "<iframe>" not in content and "<img src=x" not in content
    assert "&lt;script&gt;" in content and "&lt;iframe&gt;" in content
    assert content.count("<section>") == 3
    assert "Probability calibration" in content and "Precision–recall evidence" in content
    assert "Risk confusion matrix" in content and "Training-majority baseline" in content
    assert "@media print" in content and "<svg" in content
    assert "Complete machine-readable evidence" in content


def test_research_export_all_variants_and_no_sla_claim():
    evidence = ResearchReportService().get("porter-eta-v1")
    content, filename = export_evidence(evidence, "eta_research", "html")
    assert filename == "eta_research-porter-eta-v1.html"
    assert content.count("<section>") == 6
    assert "Load snapshot assumption" in content and "Order-only" in content
    assert "Absolute error distribution" in content and "Held-out cases" in content
    assert "No observed promised deadline" in content
    assert "export time is not training time" in content
    assert "Within ±10 min (fraction)" in content
    result = json.loads(export_evidence(evidence, "eta_research", "json")[0])
    assert result["report"]["source_audit"]["rows"] == 197428


def test_incomplete_legacy_and_invalid_formats(completed):
    with pytest.raises(ValueError, match="format"):
        export_evidence(completed, "operational", "pdf")
    with pytest.raises(ExportConflict, match="completed"):
        export_evidence({**completed, "status": "running"}, "operational", "json")
    with pytest.raises(ExportConflict, match="windows"):
        export_evidence({**completed, "report": {}}, "operational", "json")
    first = completed["report"]["windows"][0]
    del first["classification_baseline"]
    first["classification"]["metrics"]["recall"] = 0
    completed["evaluation_id"] = 'id"\r\n../unsafe'
    content, filename = export_evidence(completed, "operational", "html")
    assert "Legacy report" in content and "Accuracy alone is misleading" in content
    assert "\r" not in filename and "\n" not in filename and "/" not in filename
    assert "no plot evidence" in plot("Missing", [], "x", "y")
    assert "nan" not in plot("Finite", [(float("nan"), 1), (-1, 2)], "x", "y")


def test_export_routes_statuses_security_and_format(client, monkeypatch, tmp_path, completed):
    store = CaseRepository(tmp_path / "export.db")
    service = EvaluationService(store)
    service.save(completed)
    service.save({**completed, "evaluation_id": "running", "status": "running", "worker_id": None})
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "store", lambda: store)
    prefix = "/api/workbench/evaluations/"
    result = client.get(prefix + "safe-id/export?format=html")
    assert result.status_code == 200 and result.mimetype == "text/html"
    assert "attachment" in result.headers["Content-Disposition"]
    assert "default-src 'none'" in result.headers["Content-Security-Policy"]
    assert result.headers["X-Content-Type-Options"] == "nosniff"
    assert result.headers["Cache-Control"] == "no-store"
    assert client.get(prefix + "safe-id/export").json["report"]["kind"] == "inventory"
    assert client.get(prefix + "safe-id/export?format=pdf").status_code == 400
    assert client.get(prefix + "running/export").status_code == 409
    assert client.get(prefix + "missing/export").status_code == 404
    assert client.get("/api/workbench/research-benchmarks/porter-eta-v1/export").status_code == 200
    assert client.get("/api/workbench/research-benchmarks/unknown/export").status_code == 404
