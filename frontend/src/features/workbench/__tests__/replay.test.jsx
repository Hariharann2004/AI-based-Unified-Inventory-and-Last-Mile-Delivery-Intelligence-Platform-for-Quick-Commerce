import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
