import { useState } from "react";
import { ComparisonBars, EvidencePlot } from "../components/EvidenceCharts.jsx";
import { useRemote } from "../hooks/useRemote.js";

const number = (value) => (Number.isFinite(value) ? value.toFixed(3) : "—");

export function ResearchBenchmarkPage() {
  const [variant, setVariant] = useState("order_only");
  const [windowIndex, setWindowIndex] = useState(2);
  const listing = useRemote("/research-benchmarks");
  const id = listing.data?.reports?.[0]?.benchmark_id;
  const remote = useRemote(id ? `/research-benchmarks/${id}` : null);
  const report = remote.data?.report;
  const windows =
    report?.windows.filter((item) => item.include_load === (variant !== "order_only")) || [];
  const current = windows[windowIndex] || windows.at(-1);
  if (listing.error || remote.error)
    return (
      <p className="error" role="alert">
        {listing.error || remote.error}
      </p>
    );
  if (!report || !current)
    return (
      <div className="surface empty">
        <h2>No saved ETA evidence available</h2>
        <p>{listing.data?.message || "Loading approved research evidence…"}</p>
        <p>
          See the delivery research guide to run the offline benchmark. No serving model is changed.
        </p>
      </div>
    );
  return (
    <section>
      <div className="section-heading">
        <div>
          <h2>Porter ETA research benchmark</h2>
          <p className="muted">
            Saved, separate research evidence. Not a live delivery feed or a promoted model.
          </p>
        </div>
        <span className="mode-label">ETA regression · minutes</span>
      </div>
      <div className="surface source-controls">
        <label>
          Feature variant
          <select value={variant} onChange={(event) => setVariant(event.target.value)}>
            <option value="order_only">Order-creation inputs only</option>
            <option value="load_snapshot_assumption">
              Load snapshot assumption · research only
            </option>
          </select>
        </label>
        <label>
          Research test window
          <select
            value={windowIndex}
            onChange={(event) => setWindowIndex(Number(event.target.value))}
          >
            {windows.map((item, index) => (
              <option key={index} value={index}>
                Window {index + 1} · {item.test.rows.toLocaleString()} test records
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="warning">
        No promised deadline is present: this dataset supports ETA error measurements, not
        delay-classification accuracy. Business provenance, timezone and monetary units remain
        unverified.
      </p>
      {variant !== "order_only" && (
        <p className="warning">
          Load snapshots have unverified observation times. This variant is an opt-in research
          assumption, not safe operational evidence.
        </p>
      )}
      <div className="metrics evaluation-metrics">
        <div>
          <span>ETA MAE</span>
          <strong>
            {number(current.test.mae_minutes)}
            <small> min</small>
          </strong>
        </div>
        <div>
          <span>ETA RMSE</span>
          <strong>
            {number(current.test.rmse_minutes)}
            <small> min</small>
          </strong>
        </div>
        <div>
          <span>R² · not accuracy</span>
          <strong>{number(current.test.r2)}</strong>
        </div>
        <div>
          <span>Within ±10 minutes</span>
          <strong>{(current.test.within_10_minutes_fraction * 100).toFixed(1)}%</strong>
        </div>
      </div>
      <p className="muted">
        MAE is the average absolute error; lower is better. RMSE emphasizes large errors. The
        tolerance percentage is not classification accuracy. Negative R² is possible.
      </p>
      <div className="chart-grid">
        <ComparisonBars
          title="Test MAE versus training-only baselines · lower is better"
          unit="min"
          values={[
            { label: "LightGBM", value: current.test.mae_minutes },
            {
              label: "Training median",
              value: current.baselines.training_median.mae_minutes,
              tone: "secondary",
            },
            {
              label: "Training mean",
              value: current.baselines.training_mean.mae_minutes,
              tone: "secondary",
            },
          ]}
        />
        <ComparisonBars
          title="Absolute error distribution · all test records"
          unit="records"
          values={current.absolute_error_histogram.map((item) => ({
            label: item.interval,
            value: item.rows,
          }))}
        />
        <EvidencePlot
          title="Observed versus predicted · sampled test records"
          xLabel="Observed minutes"
          yLabel="Predicted minutes"
          points={current.sampled_test_predictions.map((item) => ({
            x: item.observed_minutes,
            y: item.predicted_minutes,
          }))}
        />
      </div>
      <div className="surface table-scroll">
        <h3>All chronological windows · selected feature variant</h3>
        <p className="muted">
          Windows overlap: these are diagnostic comparisons, not independent trials or a confidence
          interval.
        </p>
        <table>
          <thead>
            <tr>
              <th>Window</th>
              <th>Test records</th>
              <th>Model MAE (min)</th>
              <th>Median baseline MAE (min)</th>
              <th>R²</th>
            </tr>
          </thead>
          <tbody>
            {windows.map((item, index) => (
              <tr key={index}>
                <td>{index + 1}</td>
                <td>{item.test.rows.toLocaleString()}</td>
                <td>{number(item.test.mae_minutes)}</td>
                <td>{number(item.baselines.training_median.mae_minutes)}</td>
                <td>{number(item.test.r2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="surface table-scroll">
        <h3>Held-out case coverage</h3>
        <p className="muted">
          Cases overlap; extreme-duration cases use observed outcomes for diagnosis only, not as
          prediction inputs.
        </p>
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>Records</th>
              <th>Model MAE (min)</th>
              <th>Median baseline MAE (min)</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(current.test_cases).map(([name, item]) => (
              <tr key={name}>
                <td>{name.replaceAll("_", " ")}</td>
                <td>{item.rows.toLocaleString()}</td>
                <td>{number(item.model?.mae_minutes)}</td>
                <td>{number(item.training_median_baseline?.mae_minutes)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {report.warnings.map((warning) => (
        <p className="warning" key={warning}>
          {warning}
        </p>
      ))}
      <details className="surface">
        <summary>Research protocol and source provenance</summary>
        <p>
          <a href={report.source_audit.source_url} target="_blank" rel="noreferrer">
            Kaggle source listing
          </a>
        </p>
        <pre>
          {JSON.stringify(
            {
              source_audit: report.source_audit,
              protocol: report.protocol,
              selected_configuration: current.selected_configuration,
              partition: current.partition,
              features: current.features,
              library_versions: report.library_versions,
              summary: report.summary,
            },
            null,
            2,
          )}
        </pre>
        <p>
          To refresh evidence, rerun the offline CLI described in docs/delivery-research-guide.md
          and refresh this page. No automatic retraining or promotion occurs here.
        </p>
      </details>
    </section>
  );
}
