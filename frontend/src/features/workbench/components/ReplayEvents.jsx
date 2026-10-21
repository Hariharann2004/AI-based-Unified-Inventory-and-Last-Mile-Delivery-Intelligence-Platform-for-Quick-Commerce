import { useState } from "react";

const PRIORITIES = ["Critical", "High", "Normal"];
const PAGE_SIZE = 10;

export function ReplayEvents({ events, openCases, context = "replay" }) {
  const demonstration = context === "demonstration";
  const label = demonstration ? "Demonstration" : "Replay";
  const [priority, setPriority] = useState("all");
  const [sort, setSort] = useState("recorded");
  const [page, setPage] = useState(0);
  const counts = Object.fromEntries(
    PRIORITIES.map((value) => [
      value,
      events.filter((event) => event.status !== "failed" && event.priority === value).length,
    ]),
  );
  const failed = events.filter((event) => event.status === "failed").length;
  const matching = events
    .map((event, position) => ({ ...event, position }))
    .filter((event) => {
      if (priority === "all") return true;
      if (priority === "failed") return event.status === "failed";
      return event.status !== "failed" && event.priority === priority;
    })
    .sort((a, b) => {
      if (sort === "recent") return b.position - a.position;
      if (sort === "highest" || sort === "lowest") {
        const order = sort === "highest" ? PRIORITIES : [...PRIORITIES].reverse();
        const rank = (event) => {
          const value = event.status === "failed" ? -1 : order.indexOf(event.priority);
          return value === -1 ? order.length : value;
        };
        return rank(a) - rank(b) || a.position - b.position;
      }
      return a.position - b.position;
    });
  const currentPage = Math.min(page, Math.max(0, Math.ceil(matching.length / PAGE_SIZE) - 1));
  const offset = currentPage * PAGE_SIZE;
  const visible = matching.slice(offset, offset + PAGE_SIZE);

  function changeView(setValue, value) {
    setValue(value);
    setPage(0);
  }

  return (
    <section aria-labelledby={`${context}-results-title`} className="replay-results">
      <h3 id={`${context}-results-title`}>{label} results by priority</h3>
      <ul className="replay-priority-counts" aria-label={`${label} priority counts`}>
        {PRIORITIES.map((value) => (
          <li key={value}>
            <span className={`badge ${value.toLowerCase()}`}>{value}</span>
            <strong>{counts[value]}</strong>
          </li>
        ))}
        {!demonstration && (
          <li>
            <span>Processing failures</span>
            <strong>{failed}</strong>
          </li>
        )}
      </ul>
      <div className="toolbar">
        <label>
          Filter {context} priority
          <select
            value={priority}
            onChange={(event) => changeView(setPriority, event.target.value)}
          >
            <option value="all">
              {demonstration ? "All priorities" : "All priorities and failures"}
            </option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Normal">Normal</option>
            {!demonstration && <option value="failed">Processing failures</option>}
          </select>
        </label>
        <label>
          Sort {context} results
          <select value={sort} onChange={(event) => changeView(setSort, event.target.value)}>
            <option value="recorded">
              {demonstration ? "Saved selection order" : "Recorded order"}
            </option>
            <option value="recent">Most recent first</option>
            <option value="highest">Highest priority first</option>
            <option value="lowest">Lowest priority first</option>
          </select>
        </label>
      </div>
      <p className="muted">
        Priorities are Critical, High and Normal.{" "}
        {demonstration
          ? "Counts cover only the deliberately selected saved cases, not the entire dataset. No new predictions are made."
          : "Counts and filters cover all processed events in this run, not the entire dataset."}{" "}
        Filtering and sorting change the view only; they do not change predictions, replay order or
        progress.
      </p>
      <p className="provenance" role="status">
        Showing {visible.length ? `${offset + 1}–${offset + visible.length}` : "0"} of{" "}
        {matching.length} matching {demonstration ? "cases" : "events"} · {events.length}{" "}
        {demonstration ? "saved cases selected" : "events processed in this run"}
      </p>
      {!matching.length ? (
        <p className="empty">
          {demonstration
            ? "No saved cases match this priority in the selected demonstration. Filters do not create priorities."
            : !events.length
              ? "No events processed yet. Advance or start automatic replay to see results."
              : priority === "failed"
                ? "No processing failures in this run."
                : `No ${priority}-priority cases have been produced in this run. Filters do not create or change priorities.`}
        </p>
      ) : (
        <>
          <ol className="timeline" aria-label={`${label} events`}>
            {visible.map((event) => (
              <li key={event.position}>
                <div className="replay-event-heading">
                  <strong
                    className={
                      event.status === "failed"
                        ? ""
                        : `badge ${PRIORITIES.includes(event.priority) ? event.priority.toLowerCase() : ""}`
                    }
                  >
                    {event.status === "failed"
                      ? "Processing failed"
                      : event.priority
                        ? `${event.priority} priority`
                        : "Priority unavailable"}
                  </strong>
                  <small>
                    {demonstration ? "Selected case" : "Replay record"} {event.position + 1}
                  </small>
                </div>
                {event.occurred_at && (
                  <small>Recorded date: {event.occurred_at.slice(0, 10)}</small>
                )}
                {event.sku_id && (
                  <small>
                    {event.sku_id} · {event.warehouse_id}
                  </small>
                )}
                <span>{event.error || event.record_id}</span>
                {event.case_id && (
                  <button className="text-button" onClick={() => openCases(event.case_id)}>
                    Open {context} case →
                  </button>
                )}
              </li>
            ))}
          </ol>
          <div className="pagination">
            <button disabled={!currentPage} onClick={() => setPage(currentPage - 1)}>
              Previous {context} results
            </button>
            <button
              disabled={offset + PAGE_SIZE >= matching.length}
              onClick={() => setPage(currentPage + 1)}
            >
              Next {context} results
            </button>
          </div>
        </>
      )}
    </section>
  );
}
