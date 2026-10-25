"use client";

import Link from "next/link";
import { useState } from "react";
import type { ProductCardModel } from "@/lib/types";

type ProductCardProps = {
  product: ProductCardModel;
};

export function ProductCard({ product }: ProductCardProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const title = product.description?.trim() || "Untitled product";
  const showImage = Boolean(product.imageUrl) && !imageFailed && !product.unavailable;
  const category = [product.productType, product.categoryGender].filter(Boolean).join(" · ");

  return (
    <article className="product-card">
      <Link className="product-card__media" href={`/products/${encodeURIComponent(product.productId)}`}>
        {showImage ? (
          <img
            src={product.imageUrl ?? undefined}
            alt={title}
            onError={() => setImageFailed(true)}
          />
        ) : (
          <span className="product-card__fallback" aria-hidden="true">
            {(product.brand || product.productId).slice(0, 1).toUpperCase()}
          </span>
        )}
        {product.rank ? <span className="product-card__rank">{String(product.rank).padStart(2, "0")}</span> : null}
      </Link>
      <div className="product-card__body">
        {product.brand ? <p className="product-card__brand">{product.brand}</p> : null}
        <h3>
          <Link href={`/products/${encodeURIComponent(product.productId)}`}>{title}</Link>
        </h3>
        {category ? <p className="product-card__meta">{category}</p> : null}
        {product.unavailable ? <p className="product-card__meta">Details unavailable</p> : null}
      </div>
    </article>
  );
}
