"""Bounded full-import inference; durable checkpoints and cooperative cancellation."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from unified_intelligence.infrastructure.persistence.processing_repository import (
    ProcessingConflict,
    ProcessingRepository,
)

EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="uid-processing")
ADMISSION = threading.BoundedSemaphore(1)


class ProcessingService:
    def __init__(self, store, batch, *, repository=None, executor=EXECUTOR, admission=ADMISSION):
        self.store, self.batch = store, batch
        self.repository = repository or ProcessingRepository(store.path)
        self.executor, self.admission = executor, admission

    def imported(self, kind, import_id):
        imported = next(
            (
                item
                for item in self.store.imports()
                if item["kind"] == kind and item["import_id"] == import_id
            ),
            None,
        )
        if imported is None:
            raise ValueError("Select a matching dataset import first.")
        return imported

    def dispatch(self, create):
        if not self.admission.acquire(blocking=False):
            raise ProcessingConflict("Another full-import job is active in this process.")
        owner = str(uuid.uuid4())
        job = None
        try:
            job = create(owner)
            future = self.executor.submit(self.execute, job["job_id"], owner)
            future.add_done_callback(lambda _future: self.admission.release())
        except Exception:
            if job:
                self.repository.finish(
                    job["job_id"], owner, "failed", "Worker submission failed; resume explicitly."
                )
            self.admission.release()
            raise
        return job

    def start(self, kind, import_id):
        imported = self.imported(kind, import_id)
        models = self.batch.pin(kind)
        return self.dispatch(lambda owner: self.repository.create(imported, models, owner))

    def resume(self, job_id, *, retry_failed=False):
        job = self.repository.get(job_id)
        imported = self.imported(job["kind"], job["import_id"])
        models = self.batch.pin(job["kind"])
        return self.dispatch(
            lambda owner: self.repository.resume(
                job_id, imported, models, owner, retry_failed=retry_failed
            )
        )

    def execute(self, job_id, owner):
        try:
            while self.repository.heartbeat(job_id, owner):
                records = self.repository.pending_records(job_id)
                if not records:
                    job = self.repository.get(job_id)
                    self.repository.finish(
                        job_id, owner, "completed_with_errors" if job["failed"] else "completed"
                    )
                    return
                for record in records:
                    if not self.repository.heartbeat(job_id, owner):
                        break
                    case_id, error = None, None
                    try:
                        evidence = self.batch.assess(record)
                        case_id = self.store.save_case(evidence)["case_id"]
                    except Exception as failure:
                        error = f"{type(failure).__name__}: {failure}"
                    self.repository.checkpoint(
                        job_id, owner, record["record_id"], case_id=case_id, error=error
                    )
            if self.repository.get(job_id)["status"] == "cancelling":
                self.repository.finish(job_id, owner, "cancelled")
        except ProcessingConflict:
            # A stale worker must never overwrite the state of a resumed worker.
            return
        except Exception as error:
            self.repository.finish(job_id, owner, "failed", f"{type(error).__name__}: {error}")
