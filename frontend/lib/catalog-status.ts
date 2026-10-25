import type { ReadinessResponse } from "@/lib/types";

export type CatalogMode = "fixture" | "full" | "partial" | "empty" | "unknown";

export function catalogModeFromReadiness(readiness: ReadinessResponse | null): CatalogMode {
  const check = readiness?.checks.find((item) => item.name === "catalog_data");
  const message = check?.message?.toLowerCase() ?? "";
  if (!check) {
    return "unknown";
  }
  if (message.includes("fixture") || message.includes("compose-demo")) {
    return "fixture";
  }
  if (message.includes("full reference")) {
    return "full";
  }
  if (message.includes("partial")) {
    return "partial";
  }
  if (message.includes("empty")) {
    return "empty";
  }
  return "unknown";
}

export function catalogStatusLabel(mode: CatalogMode): string | null {
  if (mode === "fixture") {
    return "Demo catalog — not the full 367,172-product set";
  }
  if (mode === "full") {
    return "Full catalog";
  }
  if (mode === "partial") {
    return "Partial catalog";
  }
  if (mode === "empty") {
    return "Catalog is empty";
  }
  return null;
}
