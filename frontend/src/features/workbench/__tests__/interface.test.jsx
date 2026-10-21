import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { request } from "../api/client.js";
import { WorkbenchIcon } from "../components/WorkbenchIcon.jsx";
import { MetricCard, PanelHeading } from "../components/WorkspacePrimitives.jsx";
import { Workbench } from "../Workbench.jsx";
import { imports, inventory, scenarios } from "./fixtures.js";

vi.mock("../api/client.js", () => ({ request: vi.fn() }));
beforeEach(() => {
  request.mockReset();
  request.mockImplementation(async (path) => {
    if (path === "/imports") return imports;
    if (path === "/scenarios") return scenarios;
    if (path.startsWith("/records/")) return { records: [inventory], total: 1 };
    if (path.startsWith("/cases")) return { cases: [], total: 0 };
    return [];
  });
});

it("keeps all navigation labels accessible while decorative icons stay hidden", async () => {
  render(<Workbench />);
  const navigation = within(screen.getByRole("navigation", { name: "Workbench navigation" }));
  const labels = ["Operations", "Cases & actions", "Replay & scenarios", "Model evaluation"];
  for (const label of labels) {
    expect(navigation.getByRole("button", { name: label, exact: true })).toBeInTheDocument();
  }
  expect(navigation.getAllByRole("button")).toHaveLength(4);
  expect(navigation.queryAllByRole("img")).toHaveLength(0);
  expect(screen.getByRole("contentinfo")).toHaveTextContent(
    "Decision support, not autonomous execution.",
  );
  expect(screen.getByText("Local research environment")).toBeInTheDocument();
  expect(
    await screen.findByRole("button", { name: "Process these 1 records" }),
  ).toBeInTheDocument();
});

it("updates the visual breadcrumb and current navigation without changing page workflows", async () => {
  render(<Workbench />);
  const breadcrumb = within(screen.getByRole("group", { name: "Current section" }));
  expect(breadcrumb.getByText("Operations")).toBeInTheDocument();
  for (const [label, heading] of [
    ["Cases & actions", "Case workspace"],
    ["Replay & scenarios", "Replay & scenarios"],
    ["Model evaluation", "Model evaluation"],
    ["Operations", "Operations"],
  ]) {
    const button = screen.getByRole("button", { name: label, exact: true });
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-current", "page");
    expect(breadcrumb.getByText(label)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: heading, exact: true })).toBeInTheDocument();
  }
  expect(
    request.mock.calls.every(([, options]) => !options?.method || options.method === "GET"),
  ).toBe(true);
});

it("renders local SVG icons without external assets and safely falls back for unknown names", () => {
  const { container } = render(
    <>
      <WorkbenchIcon name="operations" />
      <WorkbenchIcon name="unknown" />
    </>,
  );
  const icons = container.querySelectorAll("svg");
  expect(icons).toHaveLength(2);
  for (const icon of icons) {
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(icon).toHaveAttribute("focusable", "false");
  }
  expect(icons[0].querySelector("path").getAttribute("d")).toBe(
    icons[1].querySelector("path").getAttribute("d"),
  );
});

it("organizes the main Operations content into working data, processing and source exploration", async () => {
  render(<Workbench />);
  expect(
    await screen.findByRole("heading", { name: "Choose your working data" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Process the whole dataset" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Source records" })).toBeInTheDocument();
  const guide = within(screen.getByRole("list", { name: "Operations workflow" }));
  expect(guide.getAllByRole("link")).toHaveLength(3);
  for (const link of guide.getAllByRole("link")) {
    expect(document.getElementById(link.getAttribute("href").slice(1))).toBeInTheDocument();
  }
  expect(screen.getByLabelText("Warehouse filter")).toBeInTheDocument();
  expect(
    await screen.findByRole("button", { name: "Process these 1 records" }),
  ).toBeInTheDocument();
  expect(
    request.mock.calls.every(([, options]) => !options?.method || options.method === "GET"),
  ).toBe(true);
});

it("keeps the three replay modes distinct and links to their actual content panels", async () => {
  render(<Workbench />);
  await userEvent.click(screen.getByRole("button", { name: "Replay & scenarios", exact: true }));
  const guide = within(screen.getByRole("list", { name: "Replay and scenario modes" }));
  expect(guide.getAllByRole("link")).toHaveLength(3);
  for (const link of guide.getAllByRole("link")) {
    expect(document.getElementById(link.getAttribute("href").slice(1))).toBeInTheDocument();
  }
  expect(screen.getByRole("region", { name: "Historical replay" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Mixed-priority demonstration" })).toBeInTheDocument();
  expect(screen.getByText(/not a representative sample/)).toBeInTheDocument();
  expect(
    request.mock.calls.every(([, options]) => !options?.method || options.method === "GET"),
  ).toBe(true);
});

it("presents supplied metric values without recalculating or relabelling them", () => {
  render(
    <>
      <PanelHeading icon="target" title="Test evidence" />
      <MetricCard icon="clock" label="Measured ETA">
        <span>12.34</span>
        <small> min</small>
      </MetricCard>
    </>,
  );
  expect(screen.getByRole("heading", { name: "Test evidence" })).toBeInTheDocument();
  expect(screen.getByText("Measured ETA")).toBeInTheDocument();
  expect(screen.getByText("12.34")).toBeInTheDocument();
  expect(screen.getByText("min")).toBeInTheDocument();
});
