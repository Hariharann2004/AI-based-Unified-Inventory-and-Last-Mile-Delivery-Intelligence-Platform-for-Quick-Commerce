import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { request } from "../api/client.js";
import { OperationsPage } from "../pages/OperationsPage.jsx";
import { delivery, imports, inventory } from "./fixtures.js";

vi.mock("../api/client.js", () => ({ request: vi.fn() }));
beforeEach(() => {
  request.mockReset();
});
function setup(options = {}) {
  const refresh = vi.fn(),
    openCases = vi.fn();
  render(
    <OperationsPage
      imports={imports}
      version={0}
      refresh={refresh}
      openCases={openCases}
      {...options}
    />,
  );
  return { refresh, openCases };
}

it("automatically loads records, filters, paginates and processes batches", async () => {
  request.mockImplementation(async (path) =>
    path === "/batches"
      ? { processed: 1, failed: 0, failures: [], results: [{ case_id: "c1" }] }
      : { total: 40, records: [inventory] },
  );
  const { openCases } = setup();
  await screen.findByText("SKU_1");
  await userEvent.type(screen.getByLabelText("Warehouse filter"), "WH_1");
  await userEvent.type(screen.getByLabelText("SKU filter"), "SKU_1");
  await waitFor(() =>
    expect(request.mock.calls.some(([path]) => path.includes("warehouse=WH_1&sku=SKU_1"))).toBe(
      true,
    ),
  );
  await userEvent.click(screen.getByRole("button", { name: "Next" }));
  await userEvent.click(screen.getByRole("button", { name: "Previous" }));
  await userEvent.click(screen.getByRole("button", { name: "Process these 1 records" }));
  expect(openCases).toHaveBeenCalledWith("c1");
});

it("imports local data and CSVs, switches types and reports per-record failures", async () => {
  request.mockImplementation(async (path, options) => {
    if (path.startsWith("/imports/")) return { ...imports[0], duplicate: !!options.data };
    if (path === "/batches")
      return { processed: 0, failed: 1, failures: [{ error: "model missing" }], results: [] };
    return { total: 25, records: path.includes("/delivery?") ? [delivery] : [inventory] };
  });
  const { refresh } = setup();
  await userEvent.click(screen.getByRole("button", { name: "Import local inventory dataset" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Import complete");
  await userEvent.upload(
    screen.getByLabelText("New CSV"),
    new File(["rows"], "new.csv", { type: "text/csv" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Import selected CSV" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Existing import reused");
  await userEvent.selectOptions(screen.getByLabelText("Record type"), "delivery");
  await screen.findByText("DEL_1");
  await userEvent.click(screen.getByRole("button", { name: "Analyze case →" }));
  expect(await screen.findByRole("status")).toHaveTextContent("model missing");
  expect(refresh).toHaveBeenCalled();
});

it("handles empty datasets and failed requests without submitting records", async () => {
  request.mockRejectedValue(new Error("API unavailable"));
  setup({ imports: [] });
  expect(screen.getByRole("button", { name: "Process these 0 records" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Import local inventory dataset" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("API unavailable");
});
