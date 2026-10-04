import { afterEach, expect, it, vi } from "vitest";
import { request } from "../api/client.js";

afterEach(() => vi.unstubAllGlobals());
it("handles JSON, upload, API errors and unreadable responses", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetch);
  await expect(request("/imports")).resolves.toEqual({ ok: true });
  await request("/batches", { method: "POST", data: { record_ids: ["1"] } });
  expect(fetch.mock.calls[1][1].headers["Content-Type"]).toBe("application/json");
  const data = new FormData();
  data.append("file", new File(["x"], "data.csv"));
  await request("/imports/inventory", { method: "POST", data });
  expect(fetch.mock.calls[2][1].body).toBe(data);
  fetch.mockResolvedValue({ ok: false, status: 400, json: async () => ({ error: "bad source" }) });
  await expect(request("/imports")).rejects.toThrow("bad source");
  fetch.mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });
  await expect(request("/imports")).rejects.toThrow("Request failed (500)");
  fetch.mockResolvedValue({
    status: 503,
    json: async () => {
      throw new Error("html");
    },
  });
  await expect(request("/imports")).rejects.toThrow("unreadable response (503)");
});
