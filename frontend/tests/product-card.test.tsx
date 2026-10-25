import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProductCard } from "@/components/ProductCard";

describe("ProductCard", () => {
  it("renders available fields and omits missing ones", () => {
    render(
      <ProductCard
        product={{
          productId: "compose-demo-003",
          description: "Puma slim fit cotton shirt navy blue formal men",
          brand: "Puma",
          productType: "shirt",
          categoryGender: "Men",
          rank: 1,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: /puma slim fit cotton shirt/i })).toBeInTheDocument();
    expect(screen.getByText("Puma")).toBeInTheDocument();
    expect(screen.getByText("shirt · Men")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /puma slim fit cotton shirt/i })).toHaveAttribute(
      "href",
      "/products/compose-demo-003",
    );
    expect(screen.queryByText(/₹|price/i)).not.toBeInTheDocument();
  });

  it("falls back when the image and optional fields are missing", () => {
    render(
      <ProductCard
        product={{
          productId: "only-id",
          imageUrl: "https://example.com/missing.jpg",
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Untitled product" })).toBeInTheDocument();
    fireEvent.error(screen.getByRole("img", { name: "Untitled product" }));
    expect(screen.getByText("O")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
