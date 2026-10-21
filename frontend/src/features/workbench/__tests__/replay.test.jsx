import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { request } from "../api/client.js";
import { ReplayPage } from "../pages/ReplayPage.jsx";
import { delivery, imports, inventory, scenarios } from "./fixtures.js";

vi.mock("../api/client.js", () => ({ request: vi.fn() }));
afterEach(() => vi.useRealTimers());
beforeEach(() => {
  request.mockReset();
  request.mockImplementation(async (path, options) => {
    if (path === "/scenarios")
      return options?.method === "POST" ? { case_id: "scenario-case" } : scenarios;
    if (path.includes("/records/inventory")) return { records: [inventory] };
    if (path.includes("/records/delivery")) return { records: [delivery] };
    if (path === "/replays")
      return {
        run_id: "r1",
        total: 10,
        cursor: 0,
        status: "ready",
        events: [],
        sequence_note: "Date then source row",
      };
    if (path.includes("/steps"))
      return {
        run_id: "r1",
        total: 10,
        cursor: options.data.expected_cursor + 5,
        status: "running",
        events: [
          { record_id: "i1:0", case_id: "c1", status: "processed", priority: "High" },
          { record_id: "bad", status: "failed", error: "Missing model" },
        ],
      };
    return {};
  });
});
function setup() {
  const refresh = vi.fn(),
    openCases = vi.fn();
  render(<ReplayPage imports={imports} version={0} refresh={refresh} openCases={openCases} />);
  return { refresh, openCases };
}

it("replays recorded steps and opens traceable cases", async () => {
  const { openCases } = setup();
  await userEvent.click(screen.getByRole("button", { name: "Prepare step-by-step replay" }));
  expect(await screen.findByText("0 / 10 records")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Advance 5 records" }));
  expect(await screen.findByText("5 / 10 records")).toBeInTheDocument();
  expect(screen.getByText("Missing model")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Open replay case →" }));
  expect(openCases).toHaveBeenCalledWith("c1");
  await userEvent.click(screen.getByRole("button", { name: "Advance 5 records" }));
  expect(await screen.findByText("10 / 10 records")).toBeInTheDocument();
});

it("requires a mapping reason for combined scenarios", async () => {
  const { openCases } = setup();
  await screen.findByRole("option", { name: "Combined pressure" });
  await userEvent.selectOptions(screen.getByLabelText("Stress scenario"), "combined_pressure");
  expect(screen.getByRole("button", { name: "Analyze stress scenario" })).toBeDisabled();
  await userEvent.type(
    screen.getByLabelText("Why these records are being mapped"),
    "Review scenario only",
  );
  await userEvent.selectOptions(screen.getByLabelText("Inventory source"), inventory.record_id);
  await userEvent.selectOptions(screen.getByLabelText("Delivery source"), delivery.record_id);
  await userEvent.click(screen.getByRole("button", { name: "Analyze stress scenario" }));
  expect(openCases).toHaveBeenCalledWith("scenario-case");
  await userEvent.selectOptions(screen.getByLabelText("Stress scenario"), "traffic_pressure");
  await userEvent.click(screen.getByRole("button", { name: "Analyze stress scenario" }));
});

it("automatically advances, pauses, and reports conflicts", async () => {
  setup();
  await userEvent.click(screen.getByRole("button", { name: "Start automatic replay" }));
  await screen.findByText("0 / 10 records");
  await userEvent.click(screen.getByRole("button", { name: "Pause replay" }));
  expect(screen.getByRole("button", { name: "Continue automatically" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Continue automatically" }));
  await waitFor(() => expect(screen.getByText("5 / 10 records")).toBeInTheDocument(), {
    timeout: 3000,
  });
  request.mockRejectedValue(new Error("Replay cursor conflict"));
  expect(await screen.findByRole("alert", {}, { timeout: 3000 })).toHaveTextContent(
    "Replay cursor conflict",
  );
});

it("does not start replay without an import", async () => {
  render(<ReplayPage imports={[]} version={0} refresh={vi.fn()} openCases={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Start automatic replay" })).toBeDisabled();
  await act(async () => {});
});

it("retains a committed cursor when paused during an in-flight step", async () => {
  setup();
  await userEvent.click(screen.getByRole("button", { name: "Start automatic replay" }));
  await screen.findByText("0 / 10 records");
  let finish;
  request.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Pause replay" }));
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "Continue automatically" }));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  fireEvent.click(screen.getByRole("button", { name: "Pause replay" }));
  expect(screen.getByRole("button", { name: "Advance 5 records" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Prepare step-by-step replay" })).toBeDisabled();
  await act(async () =>
    finish({ run_id: "r1", total: 10, cursor: 5, status: "running", events: [] }),
  );
  expect(screen.getByText("5 / 10 records")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Advance 5 records" })).toBeEnabled();
});

it("keeps filters while advancing without changing replay requests and resets views for new runs", async () => {
  const fallback = request.getMockImplementation();
  let starts = 0;
  request.mockImplementation(async (path, options) => {
    if (path === "/replays") {
      starts += 1;
      return { run_id: `run-${starts}`, total: 20, cursor: 0, status: "ready", events: [] };
    }
    if (path.includes("/steps")) {
      const cursor = options.data.expected_cursor + 5;
      return {
        run_id: "run-1",
        total: 20,
        cursor,
        status: "running",
        events: Array.from({ length: cursor }, (_, index) => ({
          record_id: `source:${index}`,
          case_id: `case-${index}`,
          status: "processed",
          priority: index % 5 === 0 ? "Critical" : "Normal",
        })),
      };
    }
    return fallback(path, options);
  });
  setup();
  await userEvent.click(screen.getByRole("button", { name: "Prepare step-by-step replay" }));
  await userEvent.selectOptions(screen.getByLabelText("Filter replay priority"), "Critical");
  await userEvent.selectOptions(screen.getByLabelText("Sort replay results"), "highest");
  await userEvent.click(screen.getByRole("button", { name: "Advance 5 records" }));
  expect(await screen.findByText("5 / 20 records")).toBeInTheDocument();
  expect(screen.getAllByText("Critical priority")).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "Advance 5 records" }));
  expect(await screen.findByText("10 / 20 records")).toBeInTheDocument();
  expect(screen.getAllByText("Critical priority")).toHaveLength(2);
  expect(screen.getByLabelText("Filter replay priority")).toHaveValue("Critical");
  expect(request).toHaveBeenCalledWith("/replays/run-1/steps", {
    method: "POST",
    data: { expected_cursor: 5, count: 5 },
  });
  await userEvent.click(screen.getByRole("button", { name: "Prepare step-by-step replay" }));
  expect(await screen.findByText("0 / 20 records")).toBeInTheDocument();
  expect(screen.getByLabelText("Filter replay priority")).toHaveValue("all");
  expect(screen.getByLabelText("Sort replay results")).toHaveValue("recorded");
  expect(request).toHaveBeenLastCalledWith("/replays", {
    method: "POST",
    data: { kind: "inventory", import_id: "i1", limit: 100 },
  });
});

it("validates date ranges and sends dates only for a new inventory replay", async () => {
  setup();
  const historical = within(screen.getByRole("region", { name: "Historical replay" }));
  fireEvent.change(screen.getByLabelText("Replay start date (optional)"), {
    target: { value: "2024-03-01" },
  });
  fireEvent.change(screen.getByLabelText("Replay end date (optional)"), {
    target: { value: "2024-02-01" },
  });
  expect(screen.getByRole("alert")).toHaveTextContent("Start date must be on or before end date.");
  expect(screen.getByRole("button", { name: "Prepare step-by-step replay" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Replay end date (optional)"), {
    target: { value: "2024-03-31" },
  });
  await userEvent.click(screen.getByRole("button", { name: "Prepare step-by-step replay" }));
  expect(request).toHaveBeenCalledWith("/replays", {
    method: "POST",
    data: {
      kind: "inventory",
      import_id: "i1",
      limit: 100,
      start_date: "2024-03-01",
      end_date: "2024-03-31",
    },
  });
  await userEvent.selectOptions(historical.getByLabelText("Record type"), "delivery");
  expect(screen.queryByLabelText("Replay start date (optional)")).not.toBeInTheDocument();
  expect(screen.getByText(/Date filtering is unavailable/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Prepare step-by-step replay" }));
  expect(request).toHaveBeenLastCalledWith("/replays", {
    method: "POST",
    data: { kind: "delivery", import_id: "d1", limit: 100 },
  });
});

it("shows the persisted date selection and eligible-record count for the active run", async () => {
  const fallback = request.getMockImplementation();
  request.mockImplementation((path, options) =>
    path === "/replays"
      ? Promise.resolve({
          run_id: "dated",
          total: 100,
          cursor: 0,
          status: "ready",
          events: [],
          date_range: { start_date: "2024-03-01", end_date: "2024-03-31" },
          eligible_records: 500,
          selected_dates: { first: "2024-03-01", last: "2024-03-10" },
        })
      : fallback(path, options),
  );
  setup();
  await userEvent.click(screen.getByRole("button", { name: "Prepare step-by-step replay" }));
  expect(await screen.findByText(/This run selects 100 of 500 eligible records/)).toHaveTextContent(
    "Recorded dates: 2024-03-01 to 2024-03-10",
  );
  expect(screen.getByText(/Requested range: 2024-03-01 to 2024-03-31/)).toBeInTheDocument();
});
