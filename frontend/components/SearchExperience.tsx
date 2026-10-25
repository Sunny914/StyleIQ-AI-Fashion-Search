"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ProductCard } from "@/components/ProductCard";
import { SearchForm } from "@/components/SearchForm";
import { ProductIqApiError, searchProducts } from "@/lib/api";
import { loadProductCards } from "@/lib/catalog";
import { SEARCH_TOP_K } from "@/lib/config";
import type { CategoryGender, ProductCardModel } from "@/lib/types";

type SearchExperienceProps = {
  query: string;
  gender: string;
};

type ViewState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "empty"; query: string; count: number }
  | { status: "ready"; query: string; count: number; cards: ProductCardModel[] }
  | { status: "error"; message: string; unavailable: boolean };

export function SearchExperience({ query, gender }: SearchExperienceProps) {
  const router = useRouter();
  const [attempt, setAttempt] = useState(0);
  const [view, setView] = useState<ViewState>({ status: query.trim() ? "loading" : "idle" });

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setView({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setView({ status: "loading" });
    (async () => {
      try {
        const categoryGender: CategoryGender | undefined =
          gender === "Men" || gender === "Women" ? gender : undefined;
        const filters = categoryGender ? { category_gender: categoryGender } : undefined;
        const response = await searchProducts(
          { query: trimmed, topK: SEARCH_TOP_K, filters },
          controller.signal,
        );
        if (controller.signal.aborted) {
          return;
        }
        if (response.results.length === 0) {
          setView({ status: "empty", query: response.query, count: response.returned_count });
          return;
        }
        const cards = await loadProductCards(
          response.results.map((item) => ({ productId: item.product_id, rank: item.rank })),
          controller.signal,
        );
        if (controller.signal.aborted) {
          return;
        }
        setView({
          status: "ready",
          query: response.query,
          count: response.returned_count,
          cards,
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        const unavailable =
          !(error instanceof ProductIqApiError) || error.kind === "network" || error.kind === "timeout";
        const message = error instanceof ProductIqApiError ? error.message : "Search failed.";
        setView({ status: "error", message, unavailable });
      }
    })();
    return () => controller.abort();
  }, [query, gender, attempt]);

  function onSearch(nextQuery: string, nextGender: CategoryGender | "") {
    const params = new URLSearchParams({ q: nextQuery });
    if (nextGender) {
      params.set("gender", nextGender);
    }
    const next = `/search?${params.toString()}`;
    const currentGender = gender === "Men" || gender === "Women" ? gender : "";
    if (nextQuery === query.trim() && nextGender === currentGender) {
      setAttempt((value) => value + 1);
      return;
    }
    router.push(next);
  }

  return (
    <section className="search-experience">
      <SearchForm
        key={`${query}:${gender}`}
        initialQuery={query}
        initialGender={gender}
        pending={view.status === "loading"}
        onSearch={onSearch}
      />
      <div aria-live="polite">
        {view.status === "loading" ? <p className="state-message" role="status">Searching the catalog…</p> : null}
        {view.status === "error" ? (
          <div className="state-message state-message--error" role="alert">
            <p>{view.message}</p>
            {view.unavailable ? <p>Search services are temporarily unavailable.</p> : null}
            <button className="retry-button" type="button" onClick={() => setAttempt((value) => value + 1)}>
              Retry search
            </button>
          </div>
        ) : null}
        {view.status === "empty" ? (
          <div className="state-message" role="status">
            <p>No pieces matched “{view.query}”.</p>
            <p>Try a broader description or clear the category filter.</p>
          </div>
        ) : null}
        {view.status === "ready" ? (
          <>
            <header className="results-heading">
              <h2>{view.query}</h2>
              <p>
                {view.count} {view.count === 1 ? "result" : "results"}
              </p>
            </header>
            <div className="product-grid">
              {view.cards.map((card) => (
                <ProductCard key={card.productId} product={card} />
              ))}
            </div>
          </>
        ) : null}
      </div>
    </section>
  );
}
