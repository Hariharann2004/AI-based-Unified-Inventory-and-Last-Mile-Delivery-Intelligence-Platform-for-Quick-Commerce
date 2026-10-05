import importlib
import json

import pytest

from unified_intelligence.application.research_report_service import ResearchReportService
from unified_intelligence.ml.evaluation.workbench import majority_baseline


def test_baseline_class_is_selected_on_training_only():
    result = majority_baseline([0, 0, 0, 1], [1, 1, 1, 0])
    assert result["predicted_label"] == 0
    assert result["metrics"]["accuracy"] == 0.25
    assert result["metrics"]["recall"] == 0
    assert majority_baseline([1, 1, 0], [0, 0])["predicted_label"] == 1


def test_research_report_approved_source_and_api(client, monkeypatch):
    service = ResearchReportService()
    result = service.get("porter-eta-v1")
    assert len(result["report"]["windows"]) == 6
    assert result["report"]["source_audit"]["promised_deadline_available"] is False
    assert result["saved_evidence"] is True
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "ResearchReportService", lambda: service)
    assert client.get("/api/workbench/research-benchmarks").json["reports"]
    assert client.get("/api/workbench/research-benchmarks/porter-eta-v1").status_code == 200
    assert client.get("/api/workbench/research-benchmarks/unknown").status_code == 404


def test_missing_and_mismatched_evidence_is_not_silently_served(tmp_path):
    service = ResearchReportService(tmp_path)
    assert not service.reports()["reports"]
    with pytest.raises(KeyError):
        service.get("../secret")
    with pytest.raises(FileNotFoundError):
        service.get("porter-eta-v1")
    (tmp_path / "reports").mkdir()
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "reports/porter_eta_benchmark.json").write_text(json.dumps({"schema_version": 1}))
    (tmp_path / "artifacts/delivery-benchmark-source.json").write_text(
        json.dumps({"csv_sha256": "expected"})
    )
    with pytest.raises(ValueError, match="source contract"):
        service.reports()
