# Full-import processing

Operations now offers **Process all N records** alongside the existing visible-page
and individual-case controls. Full import means every accepted record in the selected
import, regardless of pagination, warehouse or SKU filters. Import rejections are not
silently treated as model failures. This workflow performs inference and creates
internal cases; it does not train models or measure held-out accuracy.

## Workflow

1. Choose an inventory or delivery import, then click Process all N records.
2. The API returns a job ID immediately. A bounded local worker processes chunks
   of up to 25 records, retaining detailed evidence and saving a checkpoint per record.
3. Watch succeeded, failed, remaining and total counts. You can leave the page;
   work continues while the API process is alive. Return or refresh to recover status.
4. Cancel cooperatively: the current record finishes, then remaining records stop.
5. Resume unfinished records after cancellation, worker failure or interruption.
   Successfully checkpointed rows are skipped. Retry failed records is explicit.
6. Inspect failed records with reasons and attempts, or open the generated cases.

## Safety and runtime boundaries

- Job membership is captured transactionally at start. Source fingerprint and two
  model file identities are pinned. Workers load independent model instances once,
  avoiding per-record artifact hashing. Resume rejects changed source/model versions.
- SQLite permits only one active full-import job; a bounded executor also prevents
  unlimited in-process queues. The other synchronous page/replay workflows remain
  available; this is not a distributed scheduler or an authenticated multi-user queue.
- A 120-second lease protects active workers. After an API restart, wait up to two
  minutes for stale work to become interrupted, then resume explicitly. A live lease
  is not stolen merely because another request/process observes a different worker.
- Each attempt checks ownership. A stale worker cannot overwrite a resumed worker's
  checkpoint or terminal state. Cases use the existing idempotency key: if a crash
  occurs after case save but before checkpoint, replay reuses that case.
- Record failures do not abort other records. Worker/storage failures keep unfinished
  records pending. Retry resets failed entries only; successful cases and reviewer
  decisions remain intact. Cases still contain internal drafts, not external actions.
- Large imports create substantial evidence/case storage and may take considerable
  time. There is no performance SLA, live telemetry, automatic restart execution or
  claim of production-ready distributed durability. Keep the API local until
  authentication and authorization are implemented.

## API

`POST /api/workbench/processing-jobs` accepts `kind` and `import_id` (202).
`GET /processing-jobs?import_id=...` lists the latest 20 jobs for that import.
`GET /processing-jobs/<id>` returns persisted counts/status.
`GET /processing-jobs/<id>/items?status=failed&limit=20&offset=0` pages failures;
the limit is bounded at 100. `POST /<id>/cancel` requests cancellation.
`POST /<id>/resume` accepts `{}` or `{"retry_failed": true}` (202).
Conflicting work/version changes return 409; missing jobs return 404.

This processing contract is separate from the Porter ETA research benchmark, whose
schema is intentionally not forced into the original operational delivery model.
