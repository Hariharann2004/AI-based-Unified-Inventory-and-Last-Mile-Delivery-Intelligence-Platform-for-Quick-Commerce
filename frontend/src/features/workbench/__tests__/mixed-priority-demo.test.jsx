import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { request } from "../api/client.js";
import { MixedPriorityDemo } from "../components/MixedPriorityDemo.jsx";
import { imports } from "./fixtures.js";

vi.mock("../api/client.js", () => ({ request: vi.fn() }));
beforeEach(() => {
  request.mockReset();
});

const demonstration = {
  mode: "selected_demonstration",
  kind: "inventory",
  import_id: "i1",
  per_priority: 3,
  source: "inventory.csv",
  available_counts: { Critical: 4, High: 4, Normal: 4 },
  missing_priorities: [],
  events: ["Critical", "High", "Normal"].map((priority, index) => ({
    record_id: `i1:${index}`,
    case_id: `saved-${index}`,
    priority,
    status: "processed",
    occurred_at: `2024-0${index + 1}-01`,
    sku_id: `SKU_${index}`,
    warehouse_id: "WH_1",
  })),
};

it("loads genuine saved assessments through a read request and opens original case evidence", async () => {
  request.mockResolvedValue(demonstration);
  const openCases = vi.fn();
  render(<MixedPriorityDemo imports={imports} openCases={openCases} />);
  expect(request).not.toHaveBeenCalled();
  expect(screen.getByText(/not a representative sample/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Load mixed-priority demonstration" }));
  expect(request).toHaveBeenCalledExactlyOnceWith(
    "/replay-demonstrations?kind=inventory&import_id=i1&per_priority=3",
  );
  expect(
    await screen.findByRole("heading", { name: "Demonstration results by priority" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("3 saved cases selected");
  expect(screen.getByText("Recorded date: 2024-01-01")).toBeInTheDocument();
  expect(screen.getByText("Recorded date: 2024-03-01")).toBeInTheDocument();
  expect(screen.getByText(/Critical: 4 · High: 4 · Normal: 4/)).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "Processing failures" })).not.toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "Low", exact: true })).not.toBeInTheDocument();
  expect(
    screen.queryByRole("option", { name: "Low (Normal)", exact: true }),
  ).not.toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Filter demonstration priority"), "Critical");
  await userEvent.click(screen.getByRole("button", { name: "Open demonstration case →" }));
  expect(openCases).toHaveBeenCalledWith("saved-0");
  expect(request).toHaveBeenCalledTimes(1);
  expect(demonstration.events[0].priority).toBe("Critical");
});

it("keeps source selection explicit and allows a different per-priority size", async () => {
  request.mockResolvedValue({
    ...demonstration,
    kind: "delivery",
    import_id: "d1",
    source: "delivery.csv",
  });
  render(<MixedPriorityDemo imports={imports} openCases={vi.fn()} />);
  await userEvent.selectOptions(screen.getByLabelText("Record type"), "delivery");
  await userEvent.selectOptions(screen.getByLabelText("Dataset import"), "d1");
  await userEvent.selectOptions(screen.getByLabelText("Cases per priority"), "5");
  expect(request).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Load mixed-priority demonstration" }));
  expect(request).toHaveBeenCalledWith(
    "/replay-demonstrations?kind=delivery&import_id=d1&per_priority=5",
  );
  expect(await screen.findByText("Loaded selection: delivery · delivery.csv")).toBeInTheDocument();
});

it("does not invent absent priorities and reports load errors", async () => {
  request.mockResolvedValue({
    ...demonstration,
    events: [],
    missing_priorities: ["Critical", "High", "Normal"],
    available_counts: { Critical: 0, High: 0, Normal: 0 },
  });
  render(<MixedPriorityDemo imports={imports} openCases={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Load mixed-priority demonstration" }));
  expect(
    await screen.findByText(/No eligible saved cases for: Critical, High, Normal/),
  ).toBeInTheDocument();
  expect(screen.getByText(/No saved cases match/)).toBeInTheDocument();
  expect(screen.queryByRole("list", { name: "Demonstration events" })).not.toBeInTheDocument();
  request.mockRejectedValue(new Error("Dataset import unavailable"));
  await userEvent.click(screen.getByRole("button", { name: "Load mixed-priority demonstration" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Dataset import unavailable");
});

it("requires imports and blocks concurrent selection changes while loading", async () => {
  const view = render(<MixedPriorityDemo imports={[]} openCases={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Load mixed-priority demonstration" })).toBeDisabled();
  view.rerender(<MixedPriorityDemo imports={imports} openCases={vi.fn()} />);
  let finish;
  request.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Load mixed-priority demonstration" }));
  expect(screen.getByLabelText("Cases per priority")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Loading saved cases…" })).toBeDisabled();
  finish(demonstration);
  await waitFor(() => expect(screen.getByLabelText("Cases per priority")).toBeEnabled());
  await userEvent.selectOptions(screen.getByLabelText("Filter demonstration priority"), "Critical");
  await userEvent.selectOptions(screen.getByLabelText("Filter demonstration priority"), "High");
  expect(screen.getByText(/No new predictions are made/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Filter demonstration priority"), {
    target: { value: "Normal" },
  });
  expect(screen.getByText("Normal priority")).toBeInTheDocument();
});
