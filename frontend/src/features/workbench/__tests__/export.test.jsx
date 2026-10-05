import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { downloadReport } from "../api/client.js";
import { ExportButtons } from "../components/ExportButtons.jsx";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
it("downloads both evidence formats and revokes the blob URL", async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(["evidence"]) });
  vi.stubGlobal("fetch", fetcher);
  const create = vi.fn().mockReturnValue("blob:evidence");
  const revoke = vi.fn();
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<ExportButtons path="/evaluations/e1" filename="evaluation-e1" />);
  await userEvent.click(screen.getByRole("button", { name: "Download JSON" }));
  expect(fetcher.mock.calls[0][0]).toContain("/evaluations/e1/export?format=json");
  await userEvent.click(screen.getByRole("button", { name: "Download printable HTML" }));
  expect(fetcher.mock.calls[1][0]).toContain("format=html");
  expect(click).toHaveBeenCalledTimes(2);
  expect(revoke).toHaveBeenCalledTimes(2);
  expect(document.querySelector("a[download]")).toBeNull();
});
it("shows API export errors and handles unreadable error bodies", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ error: "Only completed evaluations can be exported." }),
    }),
  );
  render(<ExportButtons path="/evaluations/e1" filename="evidence" />);
  await userEvent.click(screen.getByRole("button", { name: "Download JSON" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Only completed evaluations");
  fetch.mockResolvedValue({
    ok: false,
    status: 503,
    json: async () => {
      throw new Error("bad body");
    },
  });
  await expect(downloadReport("/evaluations/e1", "html", "evidence")).rejects.toThrow(
    "Export failed (503)",
  );
});
