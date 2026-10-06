import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { request } from "../api/client.js";
import { DatasetLibrary } from "../components/DatasetLibrary.jsx";
import { Workbench } from "../Workbench.jsx";

vi.mock("../api/client.js", () => ({ request: vi.fn() }));
beforeEach(() => {
  request.mockReset();
});

const porter = {
  dataset_id: "porter-eta",
  title: "Porter Delivery Time Estimation",
  filename: "Porter_Delivery_Time_Estimation.csv",
  relative_path: "data/raw/Porter_Delivery_Time_Estimation.csv",
  role: "Separate ETA research benchmark",
  purpose: "Timestamp-based ETA research.",
  warning: "Porter is not a replacement for the operational delivery model.",
  available: true,
  row_count: 197428,
  size_bytes: 23759573,
  columns: ["created_at", "actual_delivery_time", "store_id"],
};
const delivery = {
  ...porter,
  dataset_id: "delivery",
  title: "Delivery operations (legacy)",
  filename: "Quick_Commerce_Delivery_Logistics.csv",
  relative_path: "data/raw/Quick_Commerce_Delivery_Logistics.csv",
  row_count: 25000,
  role: "Operational delivery (legacy)",
  warning: "Legacy rating timing remains unverified.",
};

it("shows Porter source location, original CSV link and a research shortcut", async () => {
  request.mockResolvedValue({ datasets: [delivery, porter] });
  const openResearch = vi.fn();
  render(<DatasetLibrary openResearch={openResearch} />);
  expect(await screen.findByText(porter.relative_path)).toBeInTheDocument();
  expect(screen.getByText(/197,428 original rows/)).toBeInTheDocument();
  const link = screen.getByRole("link", { name: "Download original CSV" });
  expect(link).toHaveAttribute("href", expect.stringContaining("/datasets/porter-eta/download"));
  expect(link).toHaveAttribute("download", porter.filename);
  await userEvent.click(screen.getByRole("button", { name: "View Porter ETA results" }));
  expect(openResearch).toHaveBeenCalledOnce();
  await userEvent.selectOptions(screen.getByLabelText("Project CSV dataset"), "delivery");
  expect(screen.getByText(delivery.relative_path)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "View Porter ETA results" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download original CSV" })).toHaveAttribute(
    "download",
    delivery.filename,
  );
});

it("previews literal source rows, paginates, switches sources and hides the preview", async () => {
  request.mockImplementation(async (path) => {
    if (path === "/datasets") return { datasets: [delivery, porter] };
    return {
      dataset: path.includes("/delivery/") ? delivery : porter,
      records: [{ created_at: "<original>", actual_delivery_time: "", store_id: "123" }],
    };
  });
  render(<DatasetLibrary />);
  await userEvent.click(await screen.findByRole("button", { name: "Preview original CSV" }));
  expect(await screen.findByText("<original>")).toBeInTheDocument();
  expect(screen.getByText("—")).toBeInTheDocument();
  expect(screen.getByText("1–1 of 197,428 source records")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Next CSV rows" }));
  expect(await screen.findByText("11–11 of 197,428 source records")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Previous CSV rows" }));
  expect(await screen.findByText("1–1 of 197,428 source records")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Project CSV dataset"), "delivery");
  expect(await screen.findByText("1–1 of 25,000 source records")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Hide CSV preview" }));
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(request.mock.calls.some(([path]) => path.includes("/preview?limit=10&offset=10"))).toBe(
    true,
  );
});

it("shows missing sources and connection/preview failures without enabling downloads", async () => {
  request.mockResolvedValue({
    datasets: [{ ...porter, available: false, error: "Source CSV unavailable" }],
  });
  const view = render(<DatasetLibrary />);
  expect(await screen.findByText("Source CSV unavailable")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Download original CSV" })).not.toBeInTheDocument();
  view.unmount();
  request.mockRejectedValue(new Error("Backend offline"));
  const offline = render(<DatasetLibrary />);
  expect(await screen.findByText("Dataset library: Backend offline")).toBeInTheDocument();
  offline.unmount();
  request.mockImplementation(async (path) => {
    if (path === "/datasets") return { datasets: [porter] };
    throw new Error("Source checksum mismatch");
  });
  render(<DatasetLibrary />);
  await userEvent.click(await screen.findByRole("button", { name: "Preview original CSV" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Source checksum mismatch");
});

it("opens the actual research workspace from the Operations dataset shortcut", async () => {
  request.mockImplementation(async (path) => {
    if (path === "/datasets") return { datasets: [porter] };
    if (path === "/research-benchmarks") return { reports: [] };
    return [];
  });
  render(<Workbench />);
  await userEvent.click(await screen.findByRole("button", { name: "View Porter ETA results" }));
  expect(screen.getByRole("heading", { name: "Model evaluation" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "ETA research benchmark" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(await screen.findByText("No saved ETA evidence available")).toBeInTheDocument();
});
