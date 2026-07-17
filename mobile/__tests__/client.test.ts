jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn().mockResolvedValue("stored-api-token"),
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));

import * as SecureStore from "expo-secure-store";

import { getHealth, getJobStatus, postCheckIn } from "../api/client";

describe("getHealth", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("returns the health payload on 200", async () => {
    jest.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", service: "pantryops" }),
    } as Response);

    const result = await getHealth();

    expect(result).toEqual({
      ok: true,
      data: { status: "ok", service: "pantryops" },
    });
  });

  it("returns a typed failure on network error instead of throwing", async () => {
    jest.spyOn(global, "fetch").mockRejectedValue(new TypeError("Network request failed"));

    const result = await getHealth();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBe("unreachable");
    }
  });

  it("returns a typed failure on non-2xx response", async () => {
    jest.spyOn(global, "fetch").mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({}),
    } as Response);

    const result = await getHealth();

    expect(result).toEqual({ ok: false, error: "unhealthy" });
  });
});


describe("check-in client", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("posts the silent check-in contract", async () => {
    const fetchMock = jest.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: "job-1", status: "queued", steps: [] }),
    } as Response);

    const result = await postCheckIn(["image-1", "image-2"], "session-1");

    expect(result).toEqual({
      ok: true,
      data: { jobId: "job-1", status: "queued", steps: [], error: null },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/check-in\/groceries$/),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer stored-api-token" }),
        body: JSON.stringify({
          shopping_session_id: "session-1",
          image_ids: ["image-1", "image-2"],
          processing_mode: "silent_background_enrichment",
        }),
      }),
    );
  });

  it("reads authentication from encrypted device storage", async () => {
    jest.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: "job-1", status: "queued", steps: [] }),
    } as Response);

    await postCheckIn(["image-1"], "session-1");

    expect(SecureStore.getItemAsync).toHaveBeenCalledWith("pantryops.api-token");
  });

  it("gets typed durable job status", async () => {
    jest.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        job_id: "job-1",
        status: "processing",
        steps: [{ step: "ocr", status: "queued" }],
        error: null,
      }),
    } as Response);

    const result = await getJobStatus("job-1");

    expect(result).toEqual({
      ok: true,
      data: {
        jobId: "job-1",
        status: "processing",
        steps: [{ step: "ocr", status: "queued" }],
        error: null,
      },
    });
  });
});
