import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { request } from "../api/client.js";
import { EvaluationPage } from "../pages/EvaluationPage.jsx";
import { evaluation, imports } from "./fixtures.js";

vi.mock("../api/client.js", () => ({ request: vi.fn() }));
beforeEach(() => {
  request.mockReset();
});
it("shows held-out charts, changes windows and starts evaluation", async () => {
  const refresh = vi.fn();
  request.mockImplementation(async (_path, options) =>
    options?.method === "POST" ? { status: "running" } : [evaluation],
  );
  render(<EvaluationPage imports={imports} version={0} refresh={refresh} />);
  expect(await screen.findByText("Held-out results")).toBeInTheDocument();
  expect(screen.getAllByRole("img")).toHaveLength(3);
  await userEvent.selectOptions(screen.getByLabelText("Test window"), "0");
  await userEvent.click(screen.getByRole("button", { name: "Run held-out evaluation" }));
  expect(refresh).toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Refresh reports" }));
  await userEvent.click(screen.getByText("Complete metrics and evaluation protocol"));
  await userEvent.selectOptions(screen.getByLabelText("Record type"), "delivery");
  expect(screen.getByText("No completed evaluation for this import")).toBeInTheDocument();
});

it("renders delivery evidence and API/job failures", async () => {
  request.mockResolvedValue([
    { ...evaluation, import_id: "d1" },
    {
      evaluation_id: "failed",
      import_id: "d1",
      status: "failed",
      error: "Outcome labels unavailable",
    },
  ]);
  render(<EvaluationPage imports={imports} version={0} refresh={vi.fn()} />);
  await userEvent.selectOptions(screen.getByLabelText("Record type"), "delivery");
  expect(await screen.findByText("ETA MAE")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Outcome labels unavailable");
  request.mockRejectedValue(new Error("Evaluation unavailable"));
  await userEvent.click(screen.getByRole("button", { name: "Run held-out evaluation" }));
  expect(
    screen
      .getAllByRole("alert")
      .some((node) => node.textContent.includes("Evaluation unavailable")),
  ).toBe(true);
});

it("disables submission without data and polls running jobs", async () => {
  const refresh = vi.fn();
  request.mockResolvedValue([{ import_id: "i1", status: "running" }]);
  const rendered = render(<EvaluationPage imports={[]} version={0} refresh={refresh} />);
  expect(await screen.findByRole("button", { name: "Evaluation running…" })).toBeDisabled();
  vi.useFakeTimers();
  rendered.rerender(<EvaluationPage imports={[]} version={1} refresh={refresh} />);
  await vi.advanceTimersByTimeAsync(3100);
  expect(refresh).toHaveBeenCalled();
  rendered.unmount();
  vi.useRealTimers();
});
