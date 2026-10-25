export const SEARCH_TOP_K = 12;
export const RECOMMENDATION_TOP_K = 8;
export const PRODUCT_LOOKUP_CONCURRENCY = 4;
export const REQUEST_TIMEOUT_MS = 12_000;

const DEFAULT_API_URL = "http://localhost:8000";

export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_PRODUCTIQ_API_URL?.trim();
  const value = configured && configured.length > 0 ? configured : DEFAULT_API_URL;
  return value.replace(/\/+$/, "");
}
