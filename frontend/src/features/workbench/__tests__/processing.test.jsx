import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { request } from "../api/client.js";
import { ProcessingJobs } from "../components/ProcessingJobs.jsx";
import { imports } from "./fixtures.js";

vi.mock("../api/client.js", () => ({ request: vi.fn() }));
beforeEach(() => {
  request.mockReset();
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const job = {
  job_id: "j1",
  status: "running",
  total: 40,
  processed: 10,
  succeeded: 10,
  failed: 0,
  pending: 30,
  revision: 10,
  data_fingerprint: "a".repeat(64),
};

it("starts the full import independently of visible pages and cancels cooperatively", async () => {
  let jobs = [];
  request.mockImplementation(async (path, options) => {
    if (options?.method === "POST") {
      jobs = [{ ...job, status: path.endsWith("/cancel") ? "cancelling" : "running" }];
      return jobs[0];
    }
    return { jobs };
  });
  render(<ProcessingJobs selected={imports[0]} openCases={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Process all 40 records" }));
  expect(request).toHaveBeenCalledWith("/processing-jobs", {
    method: "POST",
    data: { kind: "inventory", import_id: "i1" },
  });
  expect(await screen.findByLabelText("Full-import processing progress")).toHaveAttribute(
    "value",
    "10",
  );
  expect(screen.getByRole("button", { name: "Process all 40 records" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Cancel processing" }));
  expect(await screen.findByRole("button", { name: "Cancellation requested…" })).toBeDisabled();
});

it("resumes pending records and exposes checkpointed failures and retries", async () => {
  const openCases = vi.fn();
  request.mockImplementation(async (path, options) => {
    if (options?.method === "POST") return job;
    if (path.includes("/items?"))
      return {
        total: 21,
        items: [{ record_id: "i1:3", attempts: 1, error: "Prediction failed" }],
      };
    return { jobs: [{ ...job, status: "interrupted", failed: 1, error: "Worker lease expired" }] };
  });
  render(<ProcessingJobs selected={imports[0]} openCases={openCases} />);
  await userEvent.click(await screen.findByRole("button", { name: "Resume remaining records" }));
  expect(request).toHaveBeenCalledWith("/processing-jobs/j1/resume", { method: "POST", data: {} });
  await userEvent.click(
    await screen.findByRole("button", { name: "Retry failed records and resume" }),
  );
  expect(request).toHaveBeenCalledWith("/processing-jobs/j1/resume", {
    method: "POST",
    data: { retry_failed: true },
  });
  expect(await screen.findByText("Prediction failed")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Next failures" }));
  await waitFor(() =>
    expect(request.mock.calls.some(([path]) => path.endsWith("offset=20"))).toBe(true),
  );
  await userEvent.click(screen.getByRole("button", { name: "Previous failures" }));
  await userEvent.click(screen.getByRole("button", { name: "View generated cases →" }));
  expect(openCases).toHaveBeenCalledWith(null);
});

it("polls active jobs and stops reads on unmount", async () => {
  request.mockResolvedValue({ jobs: [job] });
  vi.useFakeTimers();
  const rendered = render(<ProcessingJobs selected={imports[0]} openCases={vi.fn()} />);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(screen.getByLabelText("Full-import processing progress")).toBeInTheDocument();
  await act(async () => vi.advanceTimersByTimeAsync(2100));
  expect(request.mock.calls.length).toBeGreaterThan(1);
  const signal = request.mock.calls.at(-1)[1].signal;
  rendered.unmount();
  expect(signal.aborted).toBe(true);
});

it("handles absent imports, completed jobs and request failures", async () => {
  const rendered = render(<ProcessingJobs selected={null} openCases={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Process all 0 records" })).toBeDisabled();
  request.mockResolvedValue({ jobs: [{ ...job, status: "completed", processed: 40, pending: 0 }] });
  rendered.rerender(<ProcessingJobs selected={imports[0]} openCases={vi.fn()} />);
  expect(await screen.findByText("completed")).toBeInTheDocument();
  expect(screen.queryByText("Cancel processing")).not.toBeInTheDocument();
  request.mockRejectedValue(new Error("Worker unavailable"));
  await userEvent.click(screen.getByRole("button", { name: "Refresh processing" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Worker unavailable");
  await userEvent.click(screen.getByRole("button", { name: "Process all 40 records" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Worker unavailable");
});

it("offers failed-only retry after a completed-with-errors job", async () => {
  request.mockImplementation(async (path) =>
    path.includes("/items?")
      ? { total: 1, items: [] }
      : { jobs: [{ ...job, status: "completed_with_errors", pending: 0, failed: 1 }] },
  );
  render(<ProcessingJobs selected={imports[0]} openCases={vi.fn()} />);
  expect(await screen.findByRole("button", { name: "Retry failed records" })).toBeEnabled();
  expect(screen.queryByText("Resume remaining records")).not.toBeInTheDocument();
});
