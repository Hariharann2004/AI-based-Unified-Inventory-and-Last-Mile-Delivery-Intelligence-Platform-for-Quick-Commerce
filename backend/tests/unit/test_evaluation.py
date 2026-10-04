import importlib
from concurrent.futures import Future
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from test_batches import Stub
from test_ingestion import DELIVERY, INVENTORY, csv_bytes

from unified_intelligence.application.evaluation_service import EvaluationService
from unified_intelligence.application.ingestion_service import IngestionService
from unified_intelligence.infrastructure.persistence.case_repository import CaseRepository
from unified_intelligence.ml.evaluation.workbench import (
    WorkbenchEvaluator,
    classification_evidence,
    date_windows,
    delivery_windows,
)


def observed_records(kind):
    rows = []
    for i in range(120):
        if kind == "inventory":
            inputs = {
                **INVENTORY,
                "Date": (date(2024, 1, 1) + timedelta(days=i // 6)).isoformat(),
                "Inventory_Level": 5 if i % 2 else 100,
            }
            outcomes = {"Units_Sold": "1"}
        else:
            inputs = {**DELIVERY, "distance_km": i + 1}
            outcomes = {"delivery_time_minutes": "25", "delayed": "yes" if i % 2 else "no"}
        rows.append({"inputs": inputs, "outcomes": outcomes})
    return rows


@pytest.mark.parametrize("kind", ["inventory", "delivery"])
def test_held_out_evaluator_protocol_and_evidence(kind):
    training_features = []

    def train(frame, _target, _task):
        training_features.append(list(frame.columns))
        return Stub()

    report = WorkbenchEvaluator(train).evaluate(observed_records(kind), kind)
    assert len(report["windows"]) == 3
    assert report["serving_models_modified"] is False
    assert len(training_features) == 6
    assert all(
        "Units_Sold" not in columns and "delivery_rating" not in columns
        for columns in training_features
    )
    final = report["windows"][-1]
    assert sum(final["counts"].values()) == 120
    assert final["classification"]["metrics"]["recall"] == 1
    assert len(final["classification"]["confusion_matrix"]) == 2
    assert final["segments"]
    assert final["samples"]


def test_date_partitions_keep_whole_dates():
    frame = pd.DataFrame([r["inputs"] for r in observed_records("inventory")])
    for train, validation, test in date_windows(frame):
        assert frame.iloc[train]["Date"].max() < frame.iloc[validation]["Date"].min()
        assert frame.iloc[validation]["Date"].max() < frame.iloc[test]["Date"].min()
    features = pd.DataFrame({"x": np.repeat(np.arange(30), 4)})
    for train, validation, test in delivery_windows(features):
        assert not set(features.iloc[train].x) & set(features.iloc[test].x)
        assert not set(features.iloc[validation].x) & set(features.iloc[test].x)


def test_evaluation_rejects_missing_targets_small_sets_and_single_class():
    evaluator = WorkbenchEvaluator(lambda *_: Stub())
    records = observed_records("inventory")
    with pytest.raises(ValueError, match="target columns"):
        evaluator.evaluate([{**r, "outcomes": {}} for r in records], "inventory")
    with pytest.raises(ValueError, match="50 records"):
        evaluator.evaluate(records[:10], "inventory")
    with pytest.raises(ValueError, match="both risk classes"):
        evaluator.evaluate(
            [{**r, "inputs": {**r["inputs"], "Inventory_Level": 1000}} for r in records],
            "inventory",
        )
    with pytest.raises(ValueError, match="10 distinct dates"):
        date_windows(pd.DataFrame({"Date": ["2024-01-01"] * 100}))
    with pytest.raises(ValueError, match="feature groups"):
        delivery_windows(pd.DataFrame({"x": [1] * 100}))
    result = classification_evidence([0, 0], [0.0, 0.2], 0.5)
    assert result["metrics"]["roc_auc"] is None
    records[0]["outcomes"]["Units_Sold"] = "invalid"
    assert evaluator.evaluate(records, "inventory")["rejected_targets"] == 1


def test_evaluation_background_persistence_and_api(client, monkeypatch, tmp_path):
    store = CaseRepository(tmp_path / "evaluation.db")
    imported = IngestionService(store).ingest(csv_bytes([INVENTORY]), "inventory", "fixture")
    service = EvaluationService(store, WorkbenchEvaluator(lambda *_: Stub()))
    jobs = importlib.import_module("unified_intelligence.application.evaluation_service")

    class InlineExecutor:
        def submit(self, function, *args):
            future = Future()
            future.set_result(function(*args))
            return future

    monkeypatch.setattr(jobs, "EXECUTOR", InlineExecutor())
    started = service.start("inventory", imported["import_id"])
    report = service.get(started["evaluation_id"])
    assert report["status"] == "failed"
    assert "50 records" in report["error"]
    assert service.reports()[0]["evaluation_id"] == started["evaluation_id"]
    with pytest.raises(KeyError):
        service.get("missing")
    with pytest.raises(ValueError):
        service.start("delivery", imported["import_id"])
    assert jobs.ADMISSION.acquire(blocking=False)
    try:
        with pytest.raises(ValueError, match="already running"):
            service.start("inventory", imported["import_id"])
    finally:
        jobs.ADMISSION.release()
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "store", lambda: store)
    assert client.get("/api/workbench/evaluations").status_code == 200
    assert client.get(f"/api/workbench/evaluations/{started['evaluation_id']}").status_code == 200
    assert (
        client.post(
            "/api/workbench/evaluations",
            json={
                "kind": "inventory",
                "import_id": imported["import_id"],
            },
        ).status_code
        == 202
    )


def test_completed_evaluation_persists_report(tmp_path):
    store = CaseRepository(tmp_path / "evaluation.db")
    rows = [{**r["inputs"], **r["outcomes"]} for r in observed_records("inventory")]
    imported = IngestionService(store).ingest(csv_bytes(rows), "inventory", "fixture")
    service = EvaluationService(store, WorkbenchEvaluator(lambda *_: Stub()))
    result = service.execute(
        {
            "evaluation_id": "fixture",
            "created_at": "2024-01-01",
            "kind": "inventory",
            "import_id": imported["import_id"],
        }
    )
    assert result["status"] == "completed"
    assert service.get("fixture")["report"]["accepted_targets"] == 120
    service.save(
        {
            "evaluation_id": "interrupted",
            "created_at": "2024-01-01",
            "status": "running",
            "worker_id": "previous-process",
        }
    )
    assert service.get("interrupted")["status"] == "failed"
