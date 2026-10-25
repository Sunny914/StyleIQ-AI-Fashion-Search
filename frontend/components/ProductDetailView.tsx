"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProductCard } from "@/components/ProductCard";
import { getProduct, getRecommendations, ProductIqApiError } from "@/lib/api";
import { loadProductCards, productToCard, withoutSeed } from "@/lib/catalog";
import { RECOMMENDATION_TOP_K } from "@/lib/config";
import type { ProductCardModel } from "@/lib/types";

type ProductDetailViewProps = {
  productId: string;
};

type DetailState =
  | { status: "loading" }
  | { status: "missing"; message: string }
  | { status: "error"; message: string }
  | { status: "ready"; product: ProductCardModel; recommendations: ProductCardModel[]; recommendationNote: string | null };

export function ProductDetailView({ productId }: ProductDetailViewProps) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<DetailState>({ status: "loading" });
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setImageFailed(false);
    setState({ status: "loading" });
    (async () => {
      try {
        const product = await getProduct(productId, controller.signal);
        let recommendations: ProductCardModel[] = [];
        let recommendationNote: string | null = null;
        try {
          const recs = await getRecommendations(product.product_id, RECOMMENDATION_TOP_K, controller.signal);
          const ranked = recs.recommendations.filter((item) => item.product_id !== product.product_id);
          if (ranked.length === 0) {
            recommendationNote = "No similar pieces were returned for this product.";
          } else {
            recommendations = withoutSeed(
              await loadProductCards(
                ranked.map((item) => ({ productId: item.product_id, rank: item.rank })),
                controller.signal,
              ),
              product.product_id,
            );
          }
        } catch (error) {
          if (controller.signal.aborted) {
            return;
          }
          recommendationNote =
            error instanceof ProductIqApiError ? error.message : "Recommendations are unavailable.";
        }
        setState({
          status: "ready",
          product: productToCard(product),
          recommendations,
          recommendationNote,
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        if (error instanceof ProductIqApiError && error.status === 404) {
          setState({ status: "missing", message: error.message });
          return;
        }
        const message = error instanceof ProductIqApiError ? error.message : "Could not load this product.";
        setState({ status: "error", message });
      }
    })();
    return () => controller.abort();
  }, [productId, attempt]);

  if (state.status === "loading") {
    return <p className="state-message" role="status">Loading product…</p>;
  }
  if (state.status === "missing") {
    return (
      <div className="state-message" role="status">
        <h2>Product not found</h2>
        <p>{state.message}</p>
        <Link href="/search">Back to search</Link>
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <div className="state-message state-message--error" role="alert">
        <p>{state.message}</p>
        <p>Search services are temporarily unavailable.</p>
        <button className="retry-button" type="button" onClick={() => setAttempt((value) => value + 1)}>
          Retry
        </button>
        <Link href="/search">Back to search</Link>
      </div>
    );
  }

  const { product, recommendations, recommendationNote } = state;
  const title = product.description?.trim() || "Untitled product";
  const category = [product.productType, product.categoryGender].filter(Boolean).join(" · ");
  const showImage = Boolean(product.imageUrl) && !imageFailed;

  return (
    <article className="product-detail">
      <div className="product-detail__layout">
        <div className="product-detail__media">
          {showImage ? (
            <img src={product.imageUrl ?? undefined} alt={title} onError={() => setImageFailed(true)} />
          ) : (
            <span className="product-card__fallback" aria-hidden="true">
              {(product.brand || product.productId).slice(0, 1).toUpperCase()}
            </span>
          )}
        </div>
        <div className="product-detail__copy">
          {product.brand ? <p className="product-card__brand">{product.brand}</p> : null}
          <h1>{title}</h1>
          {category ? <p className="product-card__meta">{category}</p> : null}
          <p className="product-detail__id">Product ID {product.productId}</p>
          {product.productUrl ? (
            <a className="text-link" href={product.productUrl} rel="noreferrer noopener" target="_blank">
              Retailer page
            </a>
          ) : null}
        </div>
      </div>
      <section className="recommendations" aria-labelledby="similar-heading">
        <p className="eyebrow">Related products</p>
        <h2 id="similar-heading">Similar pieces</h2>
        <p className="recommendations__note">Pieces returned for this product. These are catalog neighbors, not a learned preference profile.</p>
        {recommendations.length > 0 ? (
          <div className="product-grid">
            {recommendations.map((card) => (
              <ProductCard key={card.productId} product={card} />
            ))}
          </div>
        ) : (
          <p className="state-message">{recommendationNote ?? "No similar pieces were returned for this product."}</p>
        )}
      </section>
    </article>
  );
}
