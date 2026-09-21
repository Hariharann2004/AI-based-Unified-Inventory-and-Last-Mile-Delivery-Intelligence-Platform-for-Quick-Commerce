import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { DecisionDashboardPage } from "../DecisionDashboardPage.jsx";

afterEach(() => vi.unstubAllGlobals());

it("runs the demo decision and renders all result cards", async () => {
  const response = {
    inventory: { stockout_risk: "Low" },
    delivery: { delay_risk: "Medium" },
    decision: { operational_priority: "High", actions: ["Monitor delivery"] },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(response),
    }),
  );
  render(<DecisionDashboardPage />);

  await userEvent.click(screen.getByRole("button", { name: "Run demo decision" }));

  expect(await screen.findByRole("heading", { name: "Inventory" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Delivery" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Priority: High" })).toBeInTheDocument();
  expect(screen.getByText("Monitor delivery")).toBeInTheDocument();
});

it("shows a useful message when the API is unavailable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network unavailable")));
  render(<DecisionDashboardPage />);

  await userEvent.click(screen.getByRole("button", { name: "Run demo decision" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Network unavailable");
});
