import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { request } from "../api/client.js";
import { CasesPage } from "../pages/CasesPage.jsx";
import { caseRecord } from "./fixtures.js";

vi.mock("../api/client.js", () => ({ request: vi.fn() }));
beforeEach(() => {
  request.mockReset();
});
function setup(record = caseRecord, selectedId = "c1") {
  request.mockImplementation(async (path) =>
    path.startsWith("/cases?") ? { total: 40, cases: [record] } : record,
  );
  const refresh = vi.fn(),
    setSelectedId = vi.fn();
  render(
    <CasesPage
      version={0}
      refresh={refresh}
      selectedId={selectedId}
      setSelectedId={setSelectedId}
    />,
  );
  return { refresh, setSelectedId };
}

it("shows percentage risk, calculations, explanations, drafts and approvals", async () => {
  const { refresh } = setup();
  await screen.findByText(/80.00%/);
  await userEvent.click(screen.getByText("How the models arrived at this prediction"));
  expect(screen.getByText(/Raw log-odds/)).toBeInTheDocument();
  expect(screen.getByText(/Unseen categories/)).toBeInTheDocument();
  await userEvent.click(screen.getByText("Inputs, calculations and model identity"));
  await userEvent.type(screen.getByLabelText("Reviewer label"), "reviewer");
  await userEvent.type(screen.getByLabelText("Review reason"), "checked evidence");
  await userEvent.click(screen.getByRole("button", { name: "Approve internal drafts" }));
  expect(refresh).toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Dismiss with reason" }));
  await userEvent.selectOptions(screen.getByLabelText("Queue status"), "approved");
  await userEvent.click(screen.getByRole("button", { name: "Next cases" }));
  await userEvent.click(screen.getByRole("button", { name: "Previous cases" }));
});

it("displays delivery and nested simulated evidence with reviewed status", async () => {
  const record = structuredClone(caseRecord);
  record.kind = record.evidence.kind = "unified";
  record.status = "approved";
  record.evidence.mapping_reason = "Explicit review scenario";
  record.evidence.assessment = {
    inventory: caseRecord.evidence.assessment,
    delivery: caseRecord.evidence.assessment,
  };
  record.evidence.calculations = {
    inventory: caseRecord.evidence.calculations,
    delivery: caseRecord.evidence.calculations,
  };
  record.evidence.explanations = {
    delivery: {
      eta: {
        ...caseRecord.evidence.explanations.stockout,
        scale: "target_units",
        unknown_encoded_categories: [],
      },
    },
  };
  record.drafts = [{ type: "delivery_escalation", eta_minutes: 25, status: "approved" }];
  setup(record);
  expect(await screen.findByText("Combined simulated case")).toBeInTheDocument();
  expect(screen.getByText("Delivery assessment")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Case approved");
});

it("selects queued cases and handles empty detail and action errors", async () => {
  const { setSelectedId } = setup(caseRecord, null);
  await userEvent.click(await screen.findByRole("button", { name: /SKU_1/ }));
  expect(setSelectedId).toHaveBeenCalledWith("c1");
  expect(screen.getByText("Select a case")).toBeInTheDocument();
});

it("disables draft approvals when no draft exists and shows review errors", async () => {
  setup({ ...caseRecord, drafts: [] });
  await screen.findByText("No action draft is required for this case.");
  expect(screen.getByRole("button", { name: "Approve internal drafts" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Reviewer label"), "reviewer");
  await userEvent.type(screen.getByLabelText("Review reason"), "duplicate");
  request.mockRejectedValue(new Error("Already reviewed"));
  await userEvent.click(screen.getByRole("button", { name: "Dismiss with reason" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Already reviewed");
});
