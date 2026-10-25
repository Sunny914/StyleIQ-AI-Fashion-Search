export type CategoryGender = "Men" | "Women";

export type SearchFilters = {
  category_gender?: CategoryGender;
};

export type SearchResultItem = {
  product_id: string;
  rank: number;
};

export type SearchResponse = {
  query: string;
  top_k: number;
  results: SearchResultItem[];
  request_id: string;
  returned_count: number;
};

export type ProductResponse = {
  product_id: string;
  brand: string | null;
  description: string | null;
  image_url: string | null;
  product_url: string | null;
  category_gender: string | null;
  product_type: string | null;
  request_id: string;
};

export type RecommendationResultItem = {
  product_id: string;
  rank: number;
  recommendation_score: number;
};

export type RecommendationResponse = {
  seed_product_id: string;
  recommendation_type: string;
  top_k: number;
  recommendations: RecommendationResultItem[];
  request_id: string;
  returned_count: number;
};

export type HealthResponse = {
  status: string;
  service: string;
  api_version: string;
};

export type ReadinessCheck = {
  name: string;
  status: string;
  message?: string | null;
};

export type ReadinessResponse = {
  status: string;
  checks: ReadinessCheck[];
};

export type ProductCardModel = {
  productId: string;
  rank?: number;
  brand?: string | null;
  description?: string | null;
  imageUrl?: string | null;
  productUrl?: string | null;
  categoryGender?: string | null;
  productType?: string | null;
  unavailable?: boolean;
};

export type ApiErrorBody = {
  error?: {
    message?: string;
    code?: string;
  };
};
