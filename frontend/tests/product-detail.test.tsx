import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProductDetailView } from "@/components/ProductDetailView";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("ProductDetailView", () => {
  it("shows a not-found state", async () => {
    vi.stubEnv("NEXT_PUBLIC_PRODUCTIQ_API_URL", "http://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ error: { message: "Product not found." } }, 404)),
    );

    render(<ProductDetailView productId="missing" />);
    expect(await screen.findByRole("heading", { name: "Product not found" })).toBeInTheDocument();
  });

  it("renders recommendations and drops the seed product", async () => {
    vi.stubEnv("NEXT_PUBLIC_PRODUCTIQ_API_URL", "http://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const target = String(url);
        if (target.endsWith("/api/v1/recommendations")) {
          return json({
            seed_product_id: "compose-demo-001",
            recommendation_type: "similar",
            top_k: 8,
            recommendations: [
              { product_id: "compose-demo-001", rank: 1, recommendation_score: 1 },
              { product_id: "compose-demo-003", rank: 2, recommendation_score: 0.28 },
            ],
            request_id: "req",
            returned_count: 2,
          });
        }
        if (target.endsWith("/products/compose-demo-003")) {
          return json({
            product_id: "compose-demo-003",
            brand: "Puma",
            description: "Puma navy shirt",
            image_url: null,
            product_url: null,
            category_gender: "Men",
            product_type: "shirt",
            request_id: "req",
          });
        }
        if (init?.method === "GET" || target.includes("/products/compose-demo-001")) {
          return json({
            product_id: "compose-demo-001",
            brand: "Nike",
            description: "Nike running shoes",
            image_url: null,
            product_url: "https://example.com/compose-demo",
            category_gender: "Men",
            product_type: "shoes",
            request_id: "req",
          });
        }
        return json({ error: { message: "unexpected" } }, 500);
      }),
    );

    render(<ProductDetailView productId="compose-demo-001" />);
    expect(await screen.findByRole("heading", { name: "Nike running shoes" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Puma navy shirt" })).toBeInTheDocument();
    const similar = screen.getByRole("region", { name: "Similar pieces" });
    expect(similar).not.toHaveTextContent("Nike running shoes");
    expect(screen.queryByText(/0\.28/)).not.toBeInTheDocument();
  });

  it("shows a fallback when recommendations are empty", async () => {
    vi.stubEnv("NEXT_PUBLIC_PRODUCTIQ_API_URL", "http://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).endsWith("/api/v1/recommendations")) {
          return json({
            seed_product_id: "compose-demo-001",
            recommendation_type: "similar",
            top_k: 8,
            recommendations: [],
            request_id: "req",
            returned_count: 0,
          });
        }
        return json({
          product_id: "compose-demo-001",
          brand: "Nike",
          description: "Nike running shoes",
          image_url: null,
          product_url: null,
          category_gender: "Men",
          product_type: "shoes",
          request_id: "req",
        });
      }),
    );

    render(<ProductDetailView productId="compose-demo-001" />);
    expect(await screen.findByText(/No similar pieces were returned/i)).toBeInTheDocument();
  });
});
