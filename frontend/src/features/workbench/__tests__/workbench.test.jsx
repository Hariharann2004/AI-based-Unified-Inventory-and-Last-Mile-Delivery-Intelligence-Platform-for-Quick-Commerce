import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "../../../app/App.jsx";
import { request } from "../api/client.js";
import { Workbench } from "../Workbench.jsx";
import { ComparisonBars, EvidencePlot } from "../components/EvidenceCharts.jsx";
import { caseRecord, imports, inventory, scenarios } from "./fixtures.js";

vi.mock("../api/client.js", () => ({ request: vi.fn() }));
beforeEach(() => {
  request.mockReset();
});
afterEach(() => vi.restoreAllMocks());
it("uses the workflow as the default app and navigates after processing", async () => {
  request.mockImplementation(async (path) => {
    if (path === "/imports") return imports;
    if (path.startsWith("/records/")) return { total: 1, records: [inventory] };
    if (path === "/batches")
      return { processed: 1, failed: 0, failures: [], results: [{ case_id: "c1" }] };
    if (path.startsWith("/cases?")) return { total: 1, cases: [caseRecord] };
    if (path === "/cases/c1") return caseRecord;
    if (path === "/scenarios") return scenarios;
    return [];
  });
  render(<App />);
  await userEvent.click(await screen.findByRole("button", { name: "Process these 1 records" }));
  expect(await screen.findByRole("heading", { name: "Case workspace" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Replay & scenarios/ }));
  expect(screen.getByRole("heading", { name: "Replay & scenarios" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Model evaluation/ }));
  expect(screen.getByRole("heading", { name: "Model evaluation" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Operations/ }));
  expect(screen.getByRole("heading", { name: "Operations" })).toBeInTheDocument();
});

it("reports connection failures and aborts resource reads on unmount", async () => {
  request.mockRejectedValue(new Error("Backend offline"));
  const page = render(<Workbench />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Backend offline");
  const signal = request.mock.calls[0][1].signal;
  page.unmount();
  expect(signal.aborted).toBe(true);
});

it("renders accessible empty plots and zero comparison values", () => {
  render(
    <>
      <EvidencePlot points={[]} title="Empty" xLabel="x" yLabel="y" />
      <ComparisonBars title="Stock" values={[{ label: "Available", value: 0 }]} />
    </>,
  );
  expect(screen.getByText("No plot evidence for this test window.")).toBeInTheDocument();
  expect(screen.getByText("0 units")).toBeInTheDocument();
});
