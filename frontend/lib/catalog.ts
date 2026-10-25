import { getProduct } from "@/lib/api";
import { ProductIqApiError } from "@/lib/api";
import { PRODUCT_LOOKUP_CONCURRENCY } from "@/lib/config";
import type { ProductCardModel, ProductResponse } from "@/lib/types";

export function productToCard(product: ProductResponse, rank?: number): ProductCardModel {
  return {
    productId: product.product_id,
    rank,
    brand: product.brand,
    description: product.description,
    imageUrl: product.image_url,
    productUrl: product.product_url,
    categoryGender: product.category_gender,
    productType: product.product_type,
  };
}

export function unavailableCard(productId: string, rank?: number): ProductCardModel {
  return { productId, rank, unavailable: true };
}

export async function loadProductCards(
  ids: readonly { productId: string; rank?: number }[],
  signal?: AbortSignal,
): Promise<ProductCardModel[]> {
  const cards: ProductCardModel[] = new Array(ids.length);
  let cursor = 0;

  async function worker(): Promise<void> {
    while (cursor < ids.length) {
      const index = cursor;
      cursor += 1;
      const item = ids[index];
      if (!item) {
        return;
      }
      try {
        const product = await getProduct(item.productId, signal);
        cards[index] = productToCard(product, item.rank);
      } catch (error) {
        if (signal?.aborted) {
          throw error;
        }
        if (error instanceof ProductIqApiError && (error.kind === "network" || error.kind === "timeout")) {
          throw error;
        }
        cards[index] = unavailableCard(item.productId, item.rank);
      }
    }
  }

  const workers = Math.min(PRODUCT_LOOKUP_CONCURRENCY, ids.length);
  await Promise.all(Array.from({ length: workers }, () => worker()));
  return cards;
}

export function withoutSeed(cards: readonly ProductCardModel[], seedProductId: string): ProductCardModel[] {
  return cards.filter((card) => card.productId !== seedProductId);
}
