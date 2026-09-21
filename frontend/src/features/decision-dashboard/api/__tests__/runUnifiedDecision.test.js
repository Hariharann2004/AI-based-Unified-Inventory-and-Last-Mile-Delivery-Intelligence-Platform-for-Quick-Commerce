import { afterEach, describe, expect, it, vi } from "vitest";

import { runUnifiedDecision } from "../runUnifiedDecision.js";

describe("runUnifiedDecision", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts the supplied records and returns the response", async () => {
    const payload = { inventory: { SKU_ID: "SKU-1" } };
    const result = { decision: { operational_priority: "Normal" } };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(result),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(runUnifiedDecision(payload)).resolves.toEqual(result);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:5000/api/decision/unified",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) }),
    );
  });

  it("raises the API error when a request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: vi.fn().mockResolvedValue({ error: "Invalid request" }),
      }),
    );

    await expect(runUnifiedDecision({})).rejects.toThrow("Invalid request");
  });
});
