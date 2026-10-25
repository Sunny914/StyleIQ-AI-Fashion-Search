import { apiBaseUrl, REQUEST_TIMEOUT_MS } from "@/lib/config";
import type {
  ApiErrorBody,
  HealthResponse,
  ProductResponse,
  ReadinessResponse,
  RecommendationResponse,
  SearchFilters,
  SearchResponse,
} from "@/lib/types";

export type ApiFailureKind = "http" | "network" | "timeout" | "malformed";

export class ProductIqApiError extends Error {
  readonly status: number | null;
  readonly kind: ApiFailureKind;

  constructor(message: string, kind: ApiFailureKind, status: number | null = null) {
    super(message);
    this.name = "ProductIqApiError";
    this.kind = kind;
    this.status = status;
  }
}

type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
};

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  options.signal?.addEventListener("abort", onAbort);

  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: options.method ?? "GET",
      headers: options.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
    const text = await response.text();
    let payload: unknown = null;
    if (text) {
      try {
        payload = JSON.parse(text) as unknown;
      } catch {
        if (response.ok) {
          throw new ProductIqApiError("The API returned a response that was not JSON.", "malformed", response.status);
        }
      }
    }
    if (!response.ok) {
      throw new ProductIqApiError(messageFromPayload(payload, response.status), "http", response.status);
    }
    if (payload === null || typeof payload !== "object") {
      throw new ProductIqApiError("The API returned an empty response.", "malformed", response.status);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ProductIqApiError) {
      throw error;
    }
    if (options.signal?.aborted) {
      throw new ProductIqApiError("Request cancelled.", "network");
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ProductIqApiError("The API took too long to respond.", "timeout");
    }
    throw new ProductIqApiError("Could not reach the ProductIQ API.", "network");
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener("abort", onAbort);
  }
}

function messageFromPayload(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "error" in payload) {
    const message = (payload as ApiErrorBody).error?.message;
    if (message) {
      return message;
    }
  }
  if (status === 404) {
    return "Product not found.";
  }
  return `Request failed (${status}).`;
}

export async function searchProducts(
  input: { query: string; topK: number; filters?: SearchFilters },
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const body: { query: string; top_k: number; filters?: SearchFilters } = {
    query: input.query,
    top_k: input.topK,
  };
  if (input.filters && Object.keys(input.filters).length > 0) {
    body.filters = input.filters;
  }
  const payload = await requestJson<SearchResponse>("/api/v1/search", { method: "POST", body, signal });
  if (!isSearchResponse(payload)) {
    throw new ProductIqApiError("The search response was incomplete.", "malformed");
  }
  return payload;
}

export function getProduct(productId: string, signal?: AbortSignal): Promise<ProductResponse> {
  return requestJson<ProductResponse>(`/api/v1/products/${encodeURIComponent(productId)}`, { signal });
}

export function getRecommendations(
  seedProductId: string,
  topK: number,
  signal?: AbortSignal,
): Promise<RecommendationResponse> {
  return requestJson<RecommendationResponse>("/api/v1/recommendations", {
    method: "POST",
    body: { seed_product_id: seedProductId, top_k: topK },
    signal,
  });
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/v1/health", { signal });
}

export function getReadiness(signal?: AbortSignal): Promise<ReadinessResponse> {
  return requestJson<ReadinessResponse>("/api/v1/ready", { signal });
}

export function isSearchResponse(value: SearchResponse): boolean {
  return Array.isArray(value.results) && typeof value.returned_count === "number";
}
