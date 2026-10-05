import importlib
import threading
from concurrent.futures import Future

import pytest
from test_batches import make_batch
from test_ingestion import DELIVERY, INVENTORY, csv_bytes

from unified_intelligence.application.ingestion_service import IngestionService
from unified_intelligence.application.processing_service import ProcessingService
from unified_intelligence.infrastructure.persistence.case_repository import CaseRepository
from unified_intelligence.infrastructure.persistence.processing_repository import (
    LEASE_SECONDS,
    ProcessingConflict,
    ProcessingRepository,
)


class ManualExecutor:
    def __init__(self):
        self.tasks = []

    def submit(self, function, *arguments):
        future = Future()
        self.tasks.append((future, function, arguments))
        return future

    def run(self, index=0):
        future, function, arguments = self.tasks.pop(index)
        future.set_result(function(*arguments))


@pytest.fixture()
def processing(tmp_path):
    store = CaseRepository(tmp_path / "processing.db")
    imported = IngestionService(store).ingest(
        csv_bytes([{**INVENTORY, "SKU_ID": f"SKU_{index}"} for index in range(4)]),
        "inventory",
        "fixture",
    )
    clock = [1000.0]
    repository = ProcessingRepository(store.path, clock=lambda: clock[0])
    executor = ManualExecutor()
    service = ProcessingService(
        store,
        make_batch(store, tmp_path),
        repository=repository,
        executor=executor,
        admission=threading.BoundedSemaphore(1),
    )
    return service, store, repository, executor, imported, clock


def test_full_import_success_checkpoints_and_deduplicated_cases(processing):
    service, store, repository, executor, imported, _ = processing
    job = service.start("inventory", imported["import_id"])
    assert job["total"] == 4 and job["status"] == "queued"
    executor.run()
    finished = repository.get(job["job_id"])
    assert finished["status"] == "completed"
    assert finished["succeeded"] == 4 and finished["pending"] == 0
    assert finished["progress_percent"] == 100
    assert all(item["attempts"] == 1 for item in repository.items(job["job_id"])["items"])
    assert store.cases()["total"] == 4
    next_job = service.start("inventory", imported["import_id"])
    executor.run()
    assert repository.get(next_job["job_id"])["succeeded"] == 4
    assert store.cases()["total"] == 4


def test_cancel_during_record_then_resume_only_remaining(processing, monkeypatch):
    service, store, repository, executor, imported, _ = processing
    job = service.start("inventory", imported["import_id"])
    assess = service.batch.assess

    def cancel_after_first(record):
        evidence = assess(record)
        repository.cancel(job["job_id"])
        return evidence

    monkeypatch.setattr(service.batch, "assess", cancel_after_first)
    executor.run()
    cancelled = repository.get(job["job_id"])
    assert cancelled["status"] == "cancelled"
    assert cancelled["succeeded"] == 1 and cancelled["pending"] == 3
    monkeypatch.setattr(service.batch, "assess", assess)
    service.resume(job["job_id"])
    executor.run()
    assert repository.get(job["job_id"])["succeeded"] == 4
    assert store.cases()["total"] == 4
    assert all(item["attempts"] == 1 for item in repository.items(job["job_id"])["items"])


def test_record_failure_does_not_stop_import_and_explicit_retry(processing, monkeypatch):
    service, store, repository, executor, imported, _ = processing
    assess = service.batch.assess

    def fail_one(record):
        if record["position"] == 1:
            raise RuntimeError("model adapter failed")
        return assess(record)

    monkeypatch.setattr(service.batch, "assess", fail_one)
    job = service.start("inventory", imported["import_id"])
    executor.run()
    finished = repository.get(job["job_id"])
    assert finished["status"] == "completed_with_errors" and finished["failed"] == 1
    failed = repository.items(job["job_id"], status="failed")["items"]
    assert len(failed) == 1 and "RuntimeError" in failed[0]["error"]
    with pytest.raises(ProcessingConflict, match="retry"):
        service.resume(job["job_id"])
    monkeypatch.setattr(service.batch, "assess", assess)
    service.resume(job["job_id"], retry_failed=True)
    executor.run()
    assert repository.get(job["job_id"])["status"] == "completed"
    items = repository.items(job["job_id"])["items"]
    assert [item["attempts"] for item in items] == [1, 2, 1, 1]
    assert store.cases()["total"] == 4


def test_restart_lease_resume_and_old_worker_cannot_overwrite(processing):
    service, _, repository, executor, imported, clock = processing
    job = service.start("inventory", imported["import_id"])
    clock[0] += LEASE_SECONDS + 1
    assert repository.get(job["job_id"])["status"] == "interrupted"
    fresh = ProcessingService(
        service.store,
        service.batch,
        repository=repository,
        executor=executor,
        admission=threading.BoundedSemaphore(1),
    )
    fresh.resume(job["job_id"])
    executor.run(0)  # Stale old token may not cancel/overwrite the new queued worker.
    assert repository.get(job["job_id"])["status"] == "queued"
    executor.run()
    assert repository.get(job["job_id"])["status"] == "completed"


def test_admission_and_database_lock_reject_concurrent_jobs(processing):
    service, _, repository, executor, imported, _ = processing
    service.start("inventory", imported["import_id"])
    with pytest.raises(ProcessingConflict, match="active"):
        service.start("inventory", imported["import_id"])
    with pytest.raises(ProcessingConflict, match="active"):
        repository.create(imported, {}, "another-process")
    executor.run()


def test_resume_model_and_source_changes_fail_closed(processing, monkeypatch):
    service, _, repository, executor, imported, _ = processing
    job = service.start("inventory", imported["import_id"])
    repository.cancel(job["job_id"])
    executor.run()
    monkeypatch.setattr(service.batch, "pin", lambda kind: {"changed": "model"})
    with pytest.raises(ProcessingConflict, match="version"):
        service.resume(job["job_id"])
    with pytest.raises(ProcessingConflict, match="version"):
        repository.resume(
            job["job_id"], {**imported, "fingerprint": "changed"}, job["models"], "new"
        )
    assert repository.get(job["job_id"])["pending"] == 4


def test_submit_failure_preserves_resumable_job(processing, monkeypatch):
    service, _, repository, executor, imported, _ = processing
    submit = executor.submit
    monkeypatch.setattr(
        executor, "submit", lambda *args: (_ for _ in ()).throw(RuntimeError("stopped"))
    )
    with pytest.raises(RuntimeError, match="stopped"):
        service.start("inventory", imported["import_id"])
    job = repository.jobs()[0]
    assert job["status"] == "failed" and job["pending"] == 4
    monkeypatch.setattr(executor, "submit", submit)
    service.resume(job["job_id"])
    executor.run()
    assert repository.get(job["job_id"])["status"] == "completed"


def test_worker_level_failure_retains_checkpoints(processing, monkeypatch):
    service, _, repository, executor, imported, _ = processing
    monkeypatch.setattr(
        repository, "pending_records", lambda *args: (_ for _ in ()).throw(RuntimeError("database"))
    )
    job = service.start("inventory", imported["import_id"])
    executor.run()
    assert repository.get(job["job_id"])["status"] == "failed"
    assert "database" in repository.get(job["job_id"])["error"]


def test_worker_rejects_lost_checkpoint_token(processing, monkeypatch):
    service, _, repository, executor, imported, clock = processing
    assess = service.batch.assess

    def expire(record):
        evidence = assess(record)
        clock[0] += LEASE_SECONDS + 1
        return evidence

    monkeypatch.setattr(service.batch, "assess", expire)
    job = service.start("inventory", imported["import_id"])
    executor.run()
    assert repository.get(job["job_id"])["status"] == "interrupted"
    assert repository.get(job["job_id"])["pending"] == 4
    with pytest.raises(ProcessingConflict, match="lease"):
        repository.checkpoint(job["job_id"], "stale", "record")


def test_repository_missing_jobs_limits_and_import_validation(processing):
    service, _, repository, executor, imported, _ = processing
    with pytest.raises(ValueError, match="matching"):
        service.start("delivery", imported["import_id"])
    with pytest.raises(KeyError):
        repository.get("missing")
    with pytest.raises(KeyError):
        repository.resume("missing", imported, {}, "owner")
    job = service.start("inventory", imported["import_id"])
    with pytest.raises(ProcessingConflict, match="state"):
        repository.resume(job["job_id"], imported, job["models"], "owner")
    with pytest.raises(ValueError, match="status"):
        repository.items(job["job_id"], status="invalid")
    assert len(repository.items(job["job_id"], limit=1, offset=2)["items"]) == 1
    assert repository.jobs(imported["import_id"])[0]["job_id"] == job["job_id"]
    executor.run()
    assert repository.cancel(job["job_id"])["status"] == "completed"


def test_empty_import_is_rejected_transactionally(processing):
    _, store, repository, _, imported, _ = processing
    with store.connection() as connection:
        connection.execute("DELETE FROM operational_records")
    with pytest.raises(ValueError, match="no accepted"):
        repository.create(imported, {}, "owner")
    assert repository.jobs() == []


def test_api_start_progress_cancel_resume_and_validation(client, monkeypatch, processing):
    service, _, repository, executor, imported, _ = processing
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "processing_service", lambda: service)
    monkeypatch.setattr(module, "processing_repository", lambda: repository)
    root = "/api/workbench/processing-jobs"
    assert client.post(root, json={"kind": "bad", "import_id": "i"}).status_code == 422
    response = client.post(root, json={"kind": "inventory", "import_id": imported["import_id"]})
    assert response.status_code == 202
    job_id = response.get_json()["job_id"]
    assert (
        client.post(
            root, json={"kind": "inventory", "import_id": imported["import_id"]}
        ).status_code
        == 409
    )
    assert client.get(f"{root}/{job_id}").get_json()["total"] == 4
    assert client.get(root).get_json()["jobs"]
    assert client.get(f"{root}/{job_id}/items?status=pending&limit=2").get_json()["total"] == 4
    assert client.post(f"{root}/{job_id}/cancel").get_json()["status"] == "cancelling"
    executor.run()
    assert client.post(f"{root}/{job_id}/resume", json={}).status_code == 202
    executor.run()
    assert client.get(f"{root}/{job_id}").get_json()["status"] == "completed"
    assert client.get(f"{root}/missing").status_code == 404


def test_pin_detects_file_change_and_caches_worker_models(processing, tmp_path):
    service, _, _, _, _, _ = processing
    path = tmp_path / "inventory_demand.joblib"
    path.write_bytes(b"old")
    factory = service.batch.inventory_factory

    def changing_factory():
        path.write_bytes(b"new")
        return factory()

    service.batch.inventory_factory = changing_factory
    with pytest.raises(ValueError, match="changed during"):
        service.batch.pin("inventory")
    service.batch.inventory_factory = factory
    expected = service.batch.pin("inventory")
    assert expected == service.batch.pinned_models["inventory"]


def test_delivery_full_import_uses_delivery_models(processing):
    service, store, repository, executor, _, _ = processing
    imported = IngestionService(store).ingest(
        csv_bytes([{**DELIVERY, "delivery_id": f"D_{index}"} for index in range(3)]),
        "delivery",
        "delivery-fixture",
    )
    job = service.start("delivery", imported["import_id"])
    executor.run()
    assert repository.get(job["job_id"])["succeeded"] == 3
    assert set(job["models"]) == {"eta", "delay"}


def test_crash_after_case_save_reuses_case_on_resume(processing, monkeypatch):
    service, store, repository, executor, imported, _ = processing
    checkpoint = repository.checkpoint
    monkeypatch.setattr(
        repository,
        "checkpoint",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("crash")),
    )
    job = service.start("inventory", imported["import_id"])
    executor.run()
    assert repository.get(job["job_id"])["status"] == "failed"
    assert repository.get(job["job_id"])["pending"] == 4
    assert store.cases()["total"] == 1
    monkeypatch.setattr(repository, "checkpoint", checkpoint)
    service.resume(job["job_id"])
    executor.run()
    assert store.cases()["total"] == 4
    assert repository.get(job["job_id"])["succeeded"] == 4
