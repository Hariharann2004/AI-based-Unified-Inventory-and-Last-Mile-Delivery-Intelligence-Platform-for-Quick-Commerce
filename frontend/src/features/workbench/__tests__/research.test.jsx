import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { request } from "../api/client.js";
import { EvaluationInterpretation } from "../components/EvaluationInterpretation.jsx";
import { EvaluationPage } from "../pages/EvaluationPage.jsx";
import { ResearchBenchmarkPage } from "../pages/ResearchBenchmarkPage.jsx";
import { windowReport, evaluation } from "./fixtures.js";

vi.mock("../api/client.js", () => ({ request: vi.fn() }));
beforeEach(() => {
  request.mockReset();
});
const metrics = {
  rows: 100,
  mae_minutes: 12,
  rmse_minutes: 30,
  r2: -0.2,
  within_10_minutes_fraction: 0.6,
};
const window = {
  test: metrics,
  baselines: {
    training_mean: { ...metrics, mae_minutes: 15 },
    training_median: { ...metrics, mae_minutes: 14 },
  },
  include_load: false,
  absolute_error_histogram: [{ interval: "0–5", rows: 40 }],
  sampled_test_predictions: [{ observed_minutes: 40, predicted_minutes: 35 }],
  test_cases: { unseen_store: { rows: 0, model: null, training_median_baseline: null } },
};
const report = {
  windows: [window, window, window, { ...window, include_load: true }],
  source_audit: { source_url: "https://www.kaggle.com/" },
  warnings: ["Extreme durations retained"],
  summary: {},
  protocol: "Chronological",
};
it("opens a separate research area, compares baselines and switches variants", async () => {
  request.mockImplementation(async (path) =>
    path === "/evaluations"
      ? []
      : path === "/research-benchmarks"
        ? { reports: [{ benchmark_id: "porter-eta-v1" }] }
        : { report },
  );
  render(<EvaluationPage imports={[]} version={0} refresh={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "ETA research benchmark" }));
  expect(await screen.findByText("Porter ETA research benchmark")).toBeInTheDocument();
  expect(screen.getByText("R² · not accuracy")).toBeInTheDocument();
  expect(screen.getByText(/No promised deadline is present/)).toBeInTheDocument();
  expect(screen.getByText(/Windows overlap/)).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Research test window"), "0");
  await userEvent.selectOptions(
    screen.getByLabelText("Feature variant"),
    "load_snapshot_assumption",
  );
  expect(screen.getByText(/Load snapshots have unverified/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Operational evaluation" }));
  expect(screen.getByText("No completed evaluation for this import")).toBeInTheDocument();
});
it("handles missing evidence and API failures", async () => {
  request.mockResolvedValue({ reports: [], message: "Run the offline ETA benchmark CLI first." });
  const view = render(<ResearchBenchmarkPage />);
  expect(await screen.findByText("Run the offline ETA benchmark CLI first.")).toBeInTheDocument();
  view.unmount();
  request.mockRejectedValue(new Error("Source mismatch"));
  render(<ResearchBenchmarkPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Source mismatch");
});
it("warns about zero recall and distinguishes selected and action thresholds", () => {
  const current = {
    ...windowReport,
    classification: {
      ...windowReport.classification,
      metrics: { accuracy: 0.735, recall: 0, f1: 0, precision: 0 },
    },
    action_threshold: { threshold: 0.7, metrics: { recall: 0, precision: 0, f1: 0 } },
  };
  const view = render(
    <EvaluationInterpretation current={current} report={evaluation.report} kind="delivery" />,
  );
  expect(screen.getByText(/No actual risk cases were detected/)).toBeInTheDocument();
  expect(screen.getByText(/Legacy report/)).toBeInTheDocument();
  expect(screen.getByText(/action policy catches none/)).toBeInTheDocument();
  view.rerender(
    <EvaluationInterpretation
      current={{ ...current, classification_baseline: { metrics: { accuracy: 0.75 } } }}
      report={evaluation.report}
      kind="inventory"
    />,
  );
  expect(screen.queryByText(/Legacy report/)).not.toBeInTheDocument();
});
