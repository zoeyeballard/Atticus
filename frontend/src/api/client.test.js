import { describe, it, expect, vi, afterEach } from "vitest";
import { api } from "./client.js";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api client error handling", () => {
  it("parses the {error:{message}} envelope on failure", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ error: { message: "Could not find application 19999999." } }),
    });
    await expect(api.getAnalysis("x")).rejects.toThrow(/Could not find application 19999999/);
  });

  it("parses the nested detail.error envelope (FastAPI HTTPException)", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: { error: { message: "Provider not permitted." } } }),
    });
    await expect(api.analyze({})).rejects.toThrow(/Provider not permitted/);
  });

  it("returns parsed JSON on success", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ analyses: [] }),
    });
    await expect(api.listAnalyses()).resolves.toEqual({ analyses: [] });
  });
});
