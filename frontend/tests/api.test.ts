import { afterEach, describe, expect, it, vi } from "vitest";
import { getProduct, ProductIqApiError, searchProducts } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("posts search to the configured API origin", async () => {
    vi.stubEnv("NEXT_PUBLIC_PRODUCTIQ_API_URL", "http://api.test/");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        query: "navy cotton shirt",
        top_k: 12,
        results: [{ product_id: "compose-demo-003", rank: 1 }],
        request_id: "req-1",
        returned_count: 1,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await searchProducts({
      query: "navy cotton shirt",
      topK: 12,
      filters: { category_gender: "Men" },
    });

    expect(result.returned_count).toBe(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://api.test/api/v1/search");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      query: "navy cotton shirt",
      top_k: 12,
      filters: { category_gender: "Men" },
    });
  });

  it("surfaces API error messages", async () => {
    vi.stubEnv("NEXT_PUBLIC_PRODUCTIQ_API_URL", "http://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ error: { message: "Product not found." } }, 404)),
    );

    await expect(getProduct("missing")).rejects.toMatchObject({
      name: "ProductIqApiError",
      status: 404,
      kind: "http",
      message: "Product not found.",
    });
  });

  it("reports network failures", async () => {
    vi.stubEnv("NEXT_PUBLIC_PRODUCTIQ_API_URL", "http://api.test");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(searchProducts({ query: "shirt", topK: 3 })).rejects.toBeInstanceOf(ProductIqApiError);
    await expect(searchProducts({ query: "shirt", topK: 3 })).rejects.toMatchObject({ kind: "network" });
  });

  it("rejects malformed JSON", async () => {
    vi.stubEnv("NEXT_PUBLIC_PRODUCTIQ_API_URL", "http://api.test");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("nope", { status: 200 })));

    await expect(getProduct("x")).rejects.toMatchObject({ kind: "malformed" });
  });
});
