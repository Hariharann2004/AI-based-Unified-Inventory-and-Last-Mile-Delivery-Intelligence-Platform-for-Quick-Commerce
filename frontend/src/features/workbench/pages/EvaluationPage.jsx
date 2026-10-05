import { useEffect, useState } from "react";
import { request } from "../api/client.js";
import { ConfusionMatrix, EvidencePlot } from "../components/EvidenceCharts.jsx";
import { SourcePicker } from "../components/SourcePicker.jsx";
import { EvaluationInterpretation } from "../components/EvaluationInterpretation.jsx";
import { useRemote, useTask } from "../hooks/useRemote.js";
import { ResearchBenchmarkPage } from "./ResearchBenchmarkPage.jsx";

export function EvaluationPage({ imports, version, refresh }) {
  const [mode, setMode] = useState("operational");
  const [kind, setKind] = useState("inventory");
  const [importId, setImportId] = useState("");
  const [windowIndex, setWindowIndex] = useState(2);
  const selected =
    imports.find((item) => item.kind === kind && item.import_id === importId) ||
    imports.find((item) => item.kind === kind);
  const remote = useRemote("/evaluations", version);
  const task = useTask();
  const reports = (remote.data || []).filter((item) => item.import_id === selected?.import_id);
  const report = reports.find((item) => item.status === "completed")?.report;
  const current = report?.windows[windowIndex] || report?.windows.at(-1);
  const running = (remote.data || []).some((item) => item.status === "running");
  useEffect(() => {
    if (!running) return;
    const timer = setTimeout(refresh, 3000);
    return () => clearTimeout(timer);
  }, [running, refresh, version]);
  async function evaluate() {
    const result = await task.run(() =>
      request("/evaluations", { method: "POST", data: { kind, import_id: selected.import_id } }),
    );
    if (result) refresh();
  }
  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">04 / Evidence, independently measured</p>
          <h1>Model evaluation</h1>
          <p className="muted">
            Fresh temporary models. Held-out outcomes. Serving models remain unchanged.
          </p>
        </div>
        <span className="mode-label">LightGBM only</span>
      </div>
      <div className="toolbar" role="group" aria-label="Evaluation area">
        <button aria-pressed={mode === "operational"} onClick={() => setMode("operational")}>
          Operational evaluation
        </button>
        <button aria-pressed={mode === "research"} onClick={() => setMode("research")}>
          ETA research benchmark
        </button>
      </div>
      {mode === "research" ? (
        <ResearchBenchmarkPage />
      ) : (
        <>
          <div className="surface">
            <SourcePicker
              imports={imports}
              kind={kind}
              setKind={setKind}
              selected={selected}
              setSelected={setImportId}
            />
            <div className="toolbar">
              <button
                className="primary"
                disabled={task.busy || running || !selected}
                onClick={evaluate}
              >
                {running ? "Evaluation running…" : "Run held-out evaluation"}
              </button>
              <button onClick={refresh}>Refresh reports</button>
            </div>
            <p className="muted">
              Evaluates the entire import across three windows. This can take a few minutes. Jobs
              are local; an API restart interrupts unfinished jobs.
            </p>
            {(task.error || remote.error) && (
              <p className="error" role="alert">
                {task.error || remote.error}
              </p>
            )}
            {reports
              .filter((item) => item.status === "failed")
              .slice(0, 1)
              .map((item) => (
                <p key={item.evaluation_id} className="error" role="alert">
                  {item.error}
                </p>
              ))}
          </div>
          {report && current ? (
            <>
              <div className="section-heading">
                <div>
                  <h2>Held-out results</h2>
                  <p className="muted">{report.protocol}</p>
                </div>
                <label>
                  Test window
                  <select
                    value={windowIndex}
                    onChange={(event) => setWindowIndex(Number(event.target.value))}
                  >
                    {report.windows.map((item, index) => (
                      <option key={item.window} value={index}>
                        Window {item.window} · {item.counts.test.toLocaleString()} test records
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {report.warnings.map((warning) => (
                <p key={warning} className="warning">
                  {warning}
                </p>
              ))}
              <div className="metrics evaluation-metrics">
                <div>
                  <span>{kind === "inventory" ? "Demand MAE" : "ETA MAE"}</span>
                  <strong>
                    {current.regression.mae.toFixed(3)}
                    <small> {kind === "inventory" ? "units" : "min"}</small>
                  </strong>
                </div>
                <div>
                  <span>Risk precision</span>
                  <strong>{(current.classification.metrics.precision * 100).toFixed(1)}%</strong>
                </div>
                <div>
                  <span>Risk recall</span>
                  <strong>{(current.classification.metrics.recall * 100).toFixed(1)}%</strong>
                </div>
                <div>
                  <span>Risk F1</span>
                  <strong>{current.classification.metrics.f1.toFixed(3)}</strong>
                </div>
              </div>
              <p className="provenance">
                Train {current.counts.train.toLocaleString()} · validation{" "}
                {current.counts.validation.toLocaleString()} · test{" "}
                {current.counts.test.toLocaleString()} · validation-selected threshold{" "}
                {current.classification.threshold}
              </p>
              <EvaluationInterpretation current={current} report={report} kind={kind} />
              <div className="chart-grid">
                <EvidencePlot
                  title="Actual versus predicted · sampled test records"
                  xLabel={`Actual (${kind === "inventory" ? "units" : "min"})`}
                  yLabel={`Predicted (${kind === "inventory" ? "units" : "min"})`}
                  points={current.samples.map((point) => ({ x: point.actual, y: point.predicted }))}
                />
                <ConfusionMatrix matrix={current.classification.confusion_matrix} />
                <EvidencePlot
                  title="Precision–recall evidence"
                  xLabel="Recall"
                  yLabel="Precision"
                  bounded
                  points={current.classification.precision_recall.map((point) => ({
                    x: point.recall,
                    y: point.precision,
                  }))}
                />
                <EvidencePlot
                  title="Probability calibration"
                  xLabel="Mean predicted risk"
                  yLabel="Observed risk fraction"
                  bounded
                  points={current.classification.calibration.map((point) => ({
                    x: point.predicted,
                    y: point.observed,
                  }))}
                />
              </div>
              <div className="surface table-scroll">
                <h3>Segment evaluation</h3>
                <table>
                  <thead>
                    <tr>
                      <th>Segment</th>
                      <th>Test count</th>
                      <th>MAE</th>
                      <th>RMSE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {current.segments.map((item) => (
                      <tr key={item.segment}>
                        <td>{item.segment}</td>
                        <td>{item.count}</td>
                        <td>{item.mae.toFixed(3)}</td>
                        <td>{item.rmse.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <details className="surface">
                <summary>Complete metrics and evaluation protocol</summary>
                <pre>
                  {JSON.stringify(
                    {
                      protocol: report.protocol,
                      features: report.features,
                      library_versions: report.library_versions,
                      metrics: current.classification.metrics,
                      baseline: current.constant_baseline,
                      action_threshold: current.action_threshold,
                      note: report.note,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
            </>
          ) : (
            <div className="empty surface">
              <h2>No completed evaluation for this import</h2>
              <p>
                Run evaluation on records containing observed outcomes. Stress scenarios do not
                provide accuracy evidence.
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
