import { getHealth } from "../api/client";

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
