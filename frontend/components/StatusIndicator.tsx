"use client";

import { useEffect, useState } from "react";
import { getHealth, getReadiness, ProductIqApiError } from "@/lib/api";
import { catalogModeFromReadiness, catalogStatusLabel } from "@/lib/catalog-status";

type StatusState =
  | { kind: "loading" }
  | { kind: "down"; message: string }
  | { kind: "up"; ready: boolean; catalog: string | null };

export function StatusIndicator() {
  const [state, setState] = useState<StatusState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        await getHealth(controller.signal);
        try {
          const readiness = await getReadiness(controller.signal);
          setState({
            kind: "up",
            ready: readiness.status === "ready",
            catalog: catalogStatusLabel(catalogModeFromReadiness(readiness)),
          });
        } catch {
          setState({ kind: "up", ready: false, catalog: null });
        }
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        const message = error instanceof ProductIqApiError ? error.message : "API unreachable";
        setState({ kind: "down", message });
      }
    })();
    return () => controller.abort();
  }, []);

  if (state.kind === "loading") {
    return <p className="status status--quiet">Checking API…</p>;
  }
  if (state.kind === "down") {
    return <p className="status status--down">API unreachable</p>;
  }
  const parts = [state.ready ? "API ready" : "API up, search not ready"];
  if (state.catalog) {
    parts.push(state.catalog);
  }
  return <p className="status">{parts.join(" · ")}</p>;
}
