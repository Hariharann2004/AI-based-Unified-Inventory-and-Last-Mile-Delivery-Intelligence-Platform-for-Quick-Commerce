import { useEffect, useState } from "react";
import { request } from "../api/client.js";
import { useRemote, useTask } from "../hooks/useRemote.js";

const ACTIVE = ["queued", "running", "cancelling"];

export function ProcessingJobs({ selected, openCases }) {
  const [version, setVersion] = useState(0);
  const [failureOffset, setFailureOffset] = useState(0);
  const remote = useRemote(
    selected ? `/processing-jobs?import_id=${encodeURIComponent(selected.import_id)}` : null,
    version,
  );
  const task = useTask();
  const jobs = remote.data?.jobs || [];
  const job = jobs.find((item) => ACTIVE.includes(item.status)) || jobs[0];
  const active = job && ACTIVE.includes(job.status);
  const failures = useRemote(
    job?.failed
      ? `/processing-jobs/${job.job_id}/items?status=failed&limit=20&offset=${failureOffset}`
      : null,
    `${version}:${job?.revision}`,
  );
  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => setVersion((value) => value + 1), 2000);
    return () => clearTimeout(timer);
  }, [active, version]);

  async function act(path, data = {}) {
    const result = await task.run(() => request(path, { method: "POST", data }));
    if (result) {
      setFailureOffset(0);
      setVersion((value) => value + 1);
    }
  }
  return (
    <div className="surface processing-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Full import / background inference</p>
          <h2>Process the whole dataset</h2>
          <p className="muted">
            One action processes every accepted record in this import, including records outside the
            visible page and current filters. This generates cases, not accuracy scores.
          </p>
        </div>
        <button
          className="primary"
          disabled={!selected || !selected.accepted_rows || task.busy || active}
          onClick={() =>
            act("/processing-jobs", { kind: selected.kind, import_id: selected.import_id })
          }
        >
          Process all {selected?.accepted_rows.toLocaleString() || 0} records
        </button>
      </div>
      <p className="provenance">
        Bounded local worker · saved per-record checkpoints · no external actions · large imports
        can take considerable time and disk space.
      </p>
      {(remote.error || task.error || failures.error) && (
        <p className="error" role="alert">
          {remote.error || task.error || failures.error}
        </p>
      )}
      {job && (
        <div className="processing-progress">
          <p aria-live="polite">
            <strong>{job.status.replaceAll("_", " ")}</strong> · {job.processed.toLocaleString()} /{" "}
            {job.total.toLocaleString()} checked · {job.succeeded.toLocaleString()} succeeded ·{" "}
            {job.failed.toLocaleString()} failed · {job.pending.toLocaleString()} remaining
          </p>
          <progress
            aria-label="Full-import processing progress"
            value={job.processed}
            max={job.total || 1}
          />
          <p className="provenance">
            SHA-256 {job.data_fingerprint.slice(0, 12)}… · checkpoint revision {job.revision}
          </p>
          {job.error && <p className="warning">{job.error}</p>}
          <div className="toolbar">
            {active && (
              <button
                disabled={task.busy || job.status === "cancelling"}
                onClick={() => act(`/processing-jobs/${job.job_id}/cancel`)}
              >
                {job.status === "cancelling" ? "Cancellation requested…" : "Cancel processing"}
              </button>
            )}
            {["cancelled", "interrupted", "failed"].includes(job.status) && job.pending > 0 && (
              <button
                disabled={task.busy}
                onClick={() => act(`/processing-jobs/${job.job_id}/resume`)}
              >
                Resume remaining records
              </button>
            )}
            {!active && job.failed > 0 && (
              <button
                disabled={task.busy}
                onClick={() => act(`/processing-jobs/${job.job_id}/resume`, { retry_failed: true })}
              >
                Retry failed records{job.pending ? " and resume" : ""}
              </button>
            )}
            <button onClick={() => setVersion((value) => value + 1)}>Refresh processing</button>
            {job.succeeded > 0 && (
              <button onClick={() => openCases(null)}>View generated cases →</button>
            )}
          </div>
          {active && (
            <p className="muted">
              Cancellation finishes the current record. After a worker restart, allow up to two
              minutes for its lease to expire before resuming.
            </p>
          )}
          {!!failures.data?.items.length && (
            <div className="table-scroll">
              <h3>Failed records</h3>
              <table>
                <thead>
                  <tr>
                    <th>Source record</th>
                    <th>Attempts</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {failures.data.items.map((item) => (
                    <tr key={item.record_id}>
                      <td>{item.record_id}</td>
                      <td>{item.attempts}</td>
                      <td>{item.error}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="pagination">
                <span>
                  {failures.data.total} failures · showing {failureOffset + 1}–
                  {failureOffset + failures.data.items.length}
                </span>
                <button
                  disabled={!failureOffset}
                  onClick={() => setFailureOffset(Math.max(0, failureOffset - 20))}
                >
                  Previous failures
                </button>
                <button
                  disabled={failureOffset + 20 >= failures.data.total}
                  onClick={() => setFailureOffset(failureOffset + 20)}
                >
                  Next failures
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
