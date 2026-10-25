import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SearchExperience } from "@/components/SearchExperience";

const push = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("SearchExperience", () => {
  beforeEach(() => {
    push.mockReset();
    vi.stubEnv("NEXT_PUBLIC_PRODUCTIQ_API_URL", "http://api.test");
  });

  it("renders hydrated catalog cards for a search", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).endsWith("/api/v1/search")) {
          return json({
            query: "navy cotton shirt",
            top_k: 12,
            results: [{ product_id: "compose-demo-003", rank: 1 }],
            request_id: "req",
            returned_count: 1,
          });
        }
        return json({
          product_id: "compose-demo-003",
          brand: "Puma",
          description: "Puma slim fit cotton shirt navy blue formal men",
          image_url: null,
          product_url: null,
          category_gender: "Men",
          product_type: "shirt",
          request_id: "req",
        });
      }),
    );

    render(<SearchExperience query="navy cotton shirt" gender="" />);

    expect(await screen.findByRole("heading", { name: /puma slim fit cotton shirt/i })).toBeInTheDocument();
    expect(screen.getByText("1 result")).toBeInTheDocument();
    expect(screen.getByText("Puma")).toBeInTheDocument();
  });

  it("shows an empty state without inventing products", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json({
          query: "silk cape",
          top_k: 12,
          results: [],
          request_id: "req",
          returned_count: 0,
        }),
      ),
    );

    render(<SearchExperience query="silk cape" gender="" />);
    expect(await screen.findByText(/No pieces matched/i)).toBeInTheDocument();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  it("shows a recoverable error when the network fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    render(<SearchExperience query="shirt" gender="" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/Could not reach the ProductIQ API/i);
  });

  it("submits a new query through the router", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ query: "x", top_k: 12, results: [], request_id: "r", returned_count: 0 })));
    render(<SearchExperience query="" gender="" />);
    await user.type(screen.getByLabelText("Search the catalog"), "navy cotton shirt");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(push).toHaveBeenCalledWith("/search?q=navy+cotton+shirt");
  });
});
