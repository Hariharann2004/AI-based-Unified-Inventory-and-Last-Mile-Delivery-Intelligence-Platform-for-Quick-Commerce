import { useState } from "react";
import { request } from "../api/client.js";
import { ComparisonBars } from "../components/EvidenceCharts.jsx";
import { useRemote, useTask } from "../hooks/useRemote.js";

function Assessment({ evidence }) {
  if (evidence.kind === "unified")
    return (
      <>
        {["inventory", "delivery"].map((kind) => (
          <Assessment
            key={kind}
            evidence={{
              kind,
              assessment: evidence.assessment[kind],
              calculations: evidence.calculations[kind],
            }}
          />
        ))}
      </>
    );
  const assessment = evidence.assessment;
  const inventory = evidence.kind === "inventory";
  const probability = inventory ? assessment.stockout_probability : assessment.delay_probability;
  return (
    <div className="assessment-block">
      <h3>{inventory ? "Inventory assessment" : "Delivery assessment"}</h3>
      <div className="metrics">
        <div>
          <span>{inventory ? "Predicted daily demand" : "Predicted ETA"}</span>
          <strong>
            {inventory ? assessment.predicted_daily_demand : assessment.predicted_eta_minutes}{" "}
            <small>{inventory ? "units/day" : "min"}</small>
          </strong>
        </div>
        <div>
          <span>{inventory ? "Stockout risk" : "Delay risk"}</span>
          <strong>
            {(probability * 100).toFixed(2)}%{" "}
            <small>{inventory ? assessment.stockout_risk : assessment.delay_risk}</small>
          </strong>
        </div>
        <div>
          <span>{inventory ? "Health score · rule-based" : "Intelligence score · rule-based"}</span>
          <strong>
            {inventory ? assessment.inventory_health_score : assessment.delivery_intelligence_score}
            <small> / 100</small>
          </strong>
        </div>
      </div>
      <ComparisonBars
        title={inventory ? "Stock coverage calculation" : "Delivery time comparison"}
        unit={inventory ? "units" : "min"}
        values={
          inventory
            ? [
                { label: "Available stock", value: evidence.calculations.current_stock },
                {
                  label: "Required stock",
                  value: evidence.calculations.required_stock,
                  tone: "secondary",
                },
                {
                  label: "Reorder point",
                  value: evidence.calculations.reorder_point,
                  tone: "neutral",
                },
              ]
            : [
                { label: "Expected", value: evidence.calculations.expected_minutes },
                {
                  label: "Predicted",
                  value: evidence.calculations.predicted_minutes,
                  tone: "secondary",
                },
              ]
        }
      />
      <p className="formula">{evidence.calculations.formula}</p>
    </div>
  );
}

function Explanations({ explanations }) {
  return Object.entries(explanations).map(([name, info]) => {
    if (!Object.hasOwn(info, "available")) return <Explanations key={name} explanations={info} />;
    return (
      <div key={name} className="explanation">
        <h3>{name.replaceAll("_", " ")} · model contributions</h3>
        {!info.available ? (
          <p>{info.reason}</p>
        ) : (
          <>
            <p className="muted">
              {info.scale === "log_odds" ? "Raw log-odds, not percentage points" : "Target units"} ·
              baseline {info.baseline.toFixed(3)}
            </p>
            <table>
              <thead>
                <tr>
                  <th>Input factor</th>
                  <th>Contribution</th>
                </tr>
              </thead>
              <tbody>
                {info.factors.map((factor) => (
                  <tr key={factor.feature}>
                    <td>{factor.feature.replaceAll("_", " ")}</td>
                    <td>
                      {factor.contribution > 0 ? "+" : ""}
                      {factor.contribution.toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!!info.unknown_encoded_categories.length && (
              <p className="warning">
                Unseen categories: {info.unknown_encoded_categories.join(", ")}. Interpret
                cautiously.
              </p>
            )}
            <p className="muted">{info.note}</p>
          </>
        )}
      </div>
    );
  });
}

export function CasesPage({ version, refresh, selectedId, setSelectedId }) {
  const [status, setStatus] = useState("open");
  const [offset, setOffset] = useState(0);
  const [reason, setReason] = useState("");
  const [actor, setActor] = useState("");
  const queue = useRemote(`/cases?status=${status}&limit=20&offset=${offset}`, version);
  const detail = useRemote(selectedId ? `/cases/${selectedId}` : null, version);
  const task = useTask();
  const selected = detail.data;
  async function review(action) {
    const result = await task.run(() =>
      request(`/cases/${selectedId}/actions`, { method: "POST", data: { action, actor, reason } }),
    );
    if (result) refresh();
  }
  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">02 / Evidence to action</p>
          <h1>Case workspace</h1>
          <p className="muted">Review recommendations and keep a traceable internal decision.</p>
        </div>
        <label>
          Queue status
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setOffset(0);
            }}
          >
            <option value="open">Open</option>
            <option value="approved">Approved</option>
            <option value="dismissed">Dismissed</option>
            <option value="">All statuses</option>
          </select>
        </label>
      </div>
      {(queue.error || detail.error || task.error) && (
        <p role="alert" className="error">
          {queue.error || detail.error || task.error}
        </p>
      )}
      <div className="case-layout">
        <aside className="case-queue" aria-label="Prioritized case queue">
          <p className="eyebrow">{queue.data?.total || 0} cases · priority order</p>
          {(queue.data?.cases || []).map((item) => (
            <button
              className={`case-row ${item.case_id === selectedId ? "selected" : ""}`}
              key={item.case_id}
              onClick={() => {
                setSelectedId(item.case_id);
                setReason("");
              }}
            >
              <span className={`badge ${item.priority.toLowerCase()}`}>{item.priority}</span>
              <strong>
                {item.evidence.assessment.sku_id ||
                  item.evidence.assessment.delivery_id ||
                  "Combined scenario"}
              </strong>
              <small>
                {item.kind} · {item.status}
              </small>
            </button>
          ))}
          {!queue.data?.cases.length && (
            <p className="empty">No cases in this queue. Process records in Operations.</p>
          )}
          <div className="pagination">
            <button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 20))}>
              Previous cases
            </button>
            <button
              disabled={offset + 20 >= (queue.data?.total || 0)}
              onClick={() => setOffset(offset + 20)}
            >
              Next cases
            </button>
          </div>
        </aside>
        <article className="surface case-detail">
          {selected ? (
            <>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">{selected.evidence.provenance}</p>
                  <h2>
                    {selected.kind === "unified"
                      ? "Combined simulated case"
                      : `${selected.kind} decision`}
                  </h2>
                </div>
                <span className={`badge ${selected.priority.toLowerCase()}`}>
                  {selected.priority} priority
                </span>
              </div>
              <div className="recommendation">
                <p className="eyebrow">Recommended next steps</p>
                <ul>
                  {selected.evidence.decision.actions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              </div>
              {selected.evidence.mapping_reason && (
                <p className="warning">Simulated linkage: {selected.evidence.mapping_reason}</p>
              )}
              {selected.evidence.warnings.map((warning) => (
                <p key={warning} className="warning">
                  {warning}
                </p>
              ))}
              <Assessment evidence={selected.evidence} />
              <details>
                <summary>How the models arrived at this prediction</summary>
                <Explanations explanations={selected.evidence.explanations} />
              </details>
              <details>
                <summary>Inputs, calculations and model identity</summary>
                <pre>
                  {JSON.stringify(
                    {
                      inputs: selected.evidence.inputs,
                      calculations: selected.evidence.calculations,
                      models: selected.evidence.models,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
              <h3>Internal action drafts</h3>
              {selected.drafts.map((draft, index) => (
                <div className="draft" key={index}>
                  <strong>{draft.type.replaceAll("_", " ")}</strong>
                  <span>
                    {draft.quantity !== undefined
                      ? `${draft.quantity} units · ${draft.warehouse}`
                      : `ETA ${draft.eta_minutes} min`}{" "}
                    · {draft.status}
                  </span>
                </div>
              ))}
              {!selected.drafts.length && (
                <p className="muted">No action draft is required for this case.</p>
              )}
              <p className="muted">
                Approval records a local draft only. No supplier order or customer message is sent.
                Reviewer labels are not authenticated accounts.
              </p>
              {selected.status === "open" ? (
                <>
                  <div className="toolbar">
                    <label>
                      Reviewer label
                      <input
                        value={actor}
                        maxLength={80}
                        onChange={(event) => setActor(event.target.value)}
                      />
                    </label>
                    <label>
                      Review reason
                      <input
                        value={reason}
                        maxLength={500}
                        onChange={(event) => setReason(event.target.value)}
                      />
                    </label>
                  </div>
                  <div className="toolbar">
                    <button
                      className="primary"
                      disabled={task.busy || !actor.trim() || !selected.drafts.length}
                      onClick={() => review("approved")}
                    >
                      Approve internal drafts
                    </button>
                    <button
                      disabled={task.busy || !actor.trim() || !reason.trim()}
                      onClick={() => review("dismissed")}
                    >
                      Dismiss with reason
                    </button>
                  </div>
                </>
              ) : (
                <p className="notice" role="status">
                  Case {selected.status}. This review is final.
                </p>
              )}
              <h3>Audit trail</h3>
              <ol className="timeline">
                {selected.audit.map((event, index) => (
                  <li key={index}>
                    <strong>{event.event}</strong>
                    <span>
                      {event.actor} · {event.reason}
                    </span>
                    <small>{new Date(event.occurred_at).toLocaleString()}</small>
                  </li>
                ))}
              </ol>
            </>
          ) : (
            <div className="empty">
              <h2>Select a case</h2>
              <p>Its source inputs, reasoning and action history will appear here.</p>
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
