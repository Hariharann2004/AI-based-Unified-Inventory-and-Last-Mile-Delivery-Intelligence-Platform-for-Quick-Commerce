import { ComparisonBars } from "./EvidenceCharts.jsx";

const percentage = (value) => (Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—");
const score = (value) => (Number.isFinite(value) ? value.toFixed(3) : "—");

export function EvaluationInterpretation({ current, report, kind }) {
  const selected = current.classification;
  const metrics = selected.metrics;
  const baseline = current.classification_baseline;
  const matrix = selected.confusion_matrix;
  const positives = matrix[1][0] + matrix[1][1];
  const count = matrix.flat().reduce((a, b) => a + b, 0);
  const majorityShare = Math.max(matrix[0][0] + matrix[0][1], positives) / count;
  return (
    <>
      <div className="surface">
        <h3>What these scores mean</h3>
        <p>
          Accuracy counts all correct decisions. With many normal deliveries, high accuracy can
          still miss every delayed delivery. Read recall, F1 and the confusion matrix together. No
          single percentage summarizes ETA and risk models.
        </p>
        <div className="metrics evaluation-metrics">
          <div>
            <span>Risk accuracy</span>
            <strong>{percentage(metrics.accuracy)}</strong>
          </div>
          <div>
            <span>ROC AUC</span>
            <strong>{score(metrics.roc_auc)}</strong>
          </div>
          <div>
            <span>Average precision</span>
            <strong>{score(metrics.average_precision)}</strong>
          </div>
          <div>
            <span>Training-majority accuracy</span>
            <strong>{percentage(baseline?.metrics.accuracy)}</strong>
          </div>
        </div>
        {!baseline && (
          <p className="warning">
            Legacy report: rerun evaluation for a training-selected majority baseline. Test majority
            share is {percentage(majorityShare)} (descriptive only, not a trained baseline).
          </p>
        )}
        {positives > 0 && metrics.recall === 0 && (
          <p className="warning">
            No actual risk cases were detected at this threshold. Accuracy alone would be
            misleading.
          </p>
        )}
        <p className="provenance">
          Selected risk threshold: {selected.threshold}; chosen on validation only. Action
          threshold: {current.action_threshold.threshold}; a different decision policy, not another
          model.
        </p>
        {current.action_threshold.metrics && (
          <p>
            Action-policy precision {percentage(current.action_threshold.metrics.precision)} ·
            recall {percentage(current.action_threshold.metrics.recall)} · F1{" "}
            {score(current.action_threshold.metrics.f1)}.
          </p>
        )}
        {current.action_threshold.metrics?.recall === 0 && positives > 0 && (
          <p className="warning">
            The action policy catches none of the observed risk cases. Do not present its accuracy
            as successful risk detection.
          </p>
        )}
      </div>
      <ComparisonBars
        title="Regression MAE versus training-mean baseline · lower is better"
        unit={kind === "inventory" ? "units" : "min"}
        values={[
          { label: "LightGBM", value: current.regression.mae },
          { label: "Training mean", value: current.constant_baseline.mae, tone: "secondary" },
        ]}
      />
      <div className="surface table-scroll">
        <h3>All evaluation windows</h3>
        <p className="muted">
          Compare stability across windows. Do not add their counts as unique test records; splits
          can overlap.
        </p>
        <table>
          <thead>
            <tr>
              <th>Window</th>
              <th>Test count</th>
              <th>Model MAE</th>
              <th>Baseline MAE</th>
              <th>Risk accuracy</th>
              <th>Risk F1</th>
              <th>Risk recall</th>
            </tr>
          </thead>
          <tbody>
            {report.windows.map((item) => (
              <tr key={item.window}>
                <td>{item.window}</td>
                <td>{item.counts.test.toLocaleString()}</td>
                <td>{score(item.regression.mae)}</td>
                <td>{score(item.constant_baseline.mae)}</td>
                <td>{percentage(item.classification.metrics.accuracy)}</td>
                <td>{score(item.classification.metrics.f1)}</td>
                <td>{percentage(item.classification.metrics.recall)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
