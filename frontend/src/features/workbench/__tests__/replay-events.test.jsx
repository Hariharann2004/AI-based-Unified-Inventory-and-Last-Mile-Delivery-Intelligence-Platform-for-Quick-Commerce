import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { ReplayEvents } from "../components/ReplayEvents.jsx";

function event(position, priority = "Normal") {
  return {
    record_id: `source:${position}`,
    case_id: `case-${position}`,
    status: "processed",
    priority,
  };
}

function results() {
  return within(screen.getByRole("list", { name: "Replay events" })).getAllByRole("listitem");
}

it("filters all accumulated events before pagination, including older Critical cases", async () => {
  const events = [
    event(0, "Critical"),
    event(1, "High"),
    ...Array.from({ length: 13 }, (_, index) => event(index + 2)),
    { record_id: "failed-source", status: "failed", error: "Source unavailable" },
  ];
  const original = structuredClone(events);
  const openCases = vi.fn();
  render(<ReplayEvents events={events} openCases={openCases} />);

  const counts = within(screen.getByRole("list", { name: "Replay priority counts" }));
  expect(counts.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
    "Critical1",
    "High1",
    "Normal13",
    "Processing failures1",
  ]);
  expect(screen.getByRole("status")).toHaveTextContent("Showing 1–10 of 16 matching events");
  expect(screen.getByRole("button", { name: "Previous replay results" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Next replay results" }));
  expect(screen.getByRole("status")).toHaveTextContent("Showing 11–16 of 16 matching events");
  expect(screen.getByRole("button", { name: "Next replay results" })).toBeDisabled();
  expect(screen.getByText("Source unavailable")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Previous replay results" }));
  await userEvent.click(screen.getByRole("button", { name: "Next replay results" }));

  await userEvent.selectOptions(screen.getByLabelText("Filter replay priority"), "Critical");
  expect(results()).toHaveLength(1);
  expect(screen.getByText("Critical priority")).toBeInTheDocument();
  expect(screen.getByText("source:0")).toBeInTheDocument();
  expect(screen.getByText("Replay record 1")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Showing 1–1 of 1 matching events");
  await userEvent.click(screen.getByRole("button", { name: "Open replay case →" }));
  expect(openCases).toHaveBeenCalledWith("case-0");

  await userEvent.selectOptions(screen.getByLabelText("Filter replay priority"), "High");
  expect(results()).toHaveLength(1);
  expect(screen.getByText("High priority")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Filter replay priority"), "Normal");
  expect(results()).toHaveLength(10);
  expect(screen.getByRole("status")).toHaveTextContent("13 matching events");
  expect(screen.getAllByText("Normal priority")).toHaveLength(10);
  await userEvent.selectOptions(screen.getByLabelText("Filter replay priority"), "failed");
  expect(results()).toHaveLength(1);
  expect(screen.getByText("Processing failed")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Open replay case →" })).not.toBeInTheDocument();
  expect(events).toEqual(original);
});

it("sorts severity honestly, preserves ties and keeps unknown priorities and failures last", async () => {
  const events = [
    event(0),
    event(1, "High"),
    event(2, "Critical"),
    event(3, "High"),
    { record_id: "failure", status: "failed", priority: "Critical", error: "Prediction failed" },
    { record_id: "unknown", status: "processed" },
    event(6, "Unrecognized"),
  ];
  const original = structuredClone(events);
  render(<ReplayEvents events={events} openCases={vi.fn()} />);
  const positions = () =>
    results().map((item) => within(item).getByText(/Replay record/).textContent);
  await userEvent.selectOptions(screen.getByLabelText("Sort replay results"), "highest");
  expect(positions()).toEqual([3, 2, 4, 1, 5, 6, 7].map((value) => `Replay record ${value}`));
  expect(screen.getByText("Priority unavailable")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Sort replay results"), "lowest");
  expect(positions()).toEqual([1, 2, 4, 3, 5, 6, 7].map((value) => `Replay record ${value}`));
  await userEvent.selectOptions(screen.getByLabelText("Sort replay results"), "recent");
  expect(positions()).toEqual([7, 6, 5, 4, 3, 2, 1].map((value) => `Replay record ${value}`));
  await userEvent.selectOptions(screen.getByLabelText("Sort replay results"), "recorded");
  expect(positions()).toEqual([1, 2, 3, 4, 5, 6, 7].map((value) => `Replay record ${value}`));
  expect(events).toEqual(original);
});

it("resets pagination on sort changes and displays every matching case across pages", async () => {
  render(
    <ReplayEvents
      events={Array.from({ length: 25 }, (_, index) => event(index))}
      openCases={vi.fn()}
    />,
  );
  await userEvent.click(screen.getByRole("button", { name: "Next replay results" }));
  await userEvent.click(screen.getByRole("button", { name: "Next replay results" }));
  expect(results()).toHaveLength(5);
  expect(screen.getByRole("status")).toHaveTextContent("Showing 21–25 of 25 matching events");
  await userEvent.selectOptions(screen.getByLabelText("Sort replay results"), "recent");
  expect(screen.getByRole("status")).toHaveTextContent("Showing 1–10 of 25 matching events");
  expect(within(results()[0]).getByText("source:24")).toBeInTheDocument();
});

it("explains missing priorities without relabelling Normal cases or creating new results", async () => {
  const events = [event(0)];
  const { rerender } = render(<ReplayEvents events={events} openCases={vi.fn()} />);
  await userEvent.selectOptions(screen.getByLabelText("Filter replay priority"), "Critical");
  expect(screen.getByText(/No Critical-priority cases/)).toHaveTextContent(
    "Filters do not create or change priorities.",
  );
  expect(screen.queryByRole("list", { name: "Replay events" })).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent(
    "Showing 0 of 0 matching events · 1 events processed",
  );
  rerender(<ReplayEvents events={[...events, event(1, "Critical")]} openCases={vi.fn()} />);
  expect(screen.getByLabelText("Filter replay priority")).toHaveValue("Critical");
  expect(screen.getByText("Critical priority")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent(
    "Showing 1–1 of 1 matching events · 2 events processed",
  );
  await userEvent.selectOptions(screen.getByLabelText("Filter replay priority"), "failed");
  expect(screen.getByText("No processing failures in this run.")).toBeInTheDocument();
  rerender(<ReplayEvents events={[event(2, "High")]} openCases={vi.fn()} />);
  await userEvent.selectOptions(screen.getByLabelText("Filter replay priority"), "Normal");
  expect(screen.getByText(/No Normal-priority cases/)).toBeInTheDocument();
});

it("shows initial guidance before a replay processes any records", () => {
  render(<ReplayEvents events={[]} openCases={vi.fn()} />);
  expect(screen.getByText(/No events processed yet/)).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Showing 0 of 0 matching events");
  expect(screen.queryByRole("list", { name: "Replay events" })).not.toBeInTheDocument();
});
