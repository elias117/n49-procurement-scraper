"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryStates } from "nuqs";
import { searchParamsParsers } from "@/lib/search-params";
import type { SearchResponse } from "@/types/search";
import { API_PUBLIC } from "@/lib/api";

/**
 * Core search hook: syncs all 16 search params with the URL via nuqs
 * and fetches results from the FastAPI search endpoint.
 *
 * Uses history: "push" so browser back/forward navigates search history.
 */
export function useSearch() {
  const [params, setParams] = useQueryStates(searchParamsParsers, {
    history: "push",
  });

  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Track the latest fetch to avoid stale responses
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Cancel any in-flight request
    if (abortRef.current) {
      abortRef.current.abort();
    }

    const controller = new AbortController();
    abortRef.current = controller;

    async function fetchResults() {
      setLoading(true);
      setError(null);

      try {
        const searchParams = new URLSearchParams();

        // Scalar params -- skip defaults to keep URL clean
        if (params.q) searchParams.set("q", params.q);
        if (params.mode !== "hybrid") searchParams.set("mode", params.mode);
        if (params.page !== 1)
          searchParams.set("page", String(params.page));
        if (params.page_size !== 25)
          searchParams.set("page_size", String(params.page_size));
        if (params.sort_by !== "relevance")
          searchParams.set("sort_by", params.sort_by);
        if (params.sort_order !== "desc")
          searchParams.set("sort_order", params.sort_order);
        if (params.include_closed)
          searchParams.set("include_closed", "true");

        // Array params -- FastAPI expects repeated query params
        for (const region of params.regions) {
          searchParams.append("regions", region);
        }
        for (const portal of params.portals) {
          searchParams.append("portals", portal);
        }
        for (const code of params.classification_codes) {
          searchParams.append("classification_codes", code);
        }

        // Date params -- only add if not null
        if (params.closing_date_from) {
          searchParams.set(
            "closing_date_from",
            params.closing_date_from.toISOString()
          );
        }
        if (params.closing_date_to) {
          searchParams.set(
            "closing_date_to",
            params.closing_date_to.toISOString()
          );
        }
        if (params.posting_date_from) {
          searchParams.set(
            "posting_date_from",
            params.posting_date_from.toISOString()
          );
        }
        if (params.posting_date_to) {
          searchParams.set(
            "posting_date_to",
            params.posting_date_to.toISOString()
          );
        }

        // Numeric params -- only add if not null
        if (params.value_min != null) {
          searchParams.set("value_min", String(params.value_min));
        }
        if (params.value_max != null) {
          searchParams.set("value_max", String(params.value_max));
        }

        const url = `${API_PUBLIC}/search?${searchParams.toString()}`;
        const res = await fetch(url, { signal: controller.signal });

        if (!res.ok) {
          throw new Error(`Search failed: ${res.status} ${res.statusText}`);
        }

        const json: SearchResponse = await res.json();
        setData(json);
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // Request was cancelled -- ignore
          return;
        }
        setError(
          err instanceof Error ? err.message : "An unexpected error occurred"
        );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    fetchResults();

    return () => {
      controller.abort();
    };
  }, [params]);

  /**
   * Set a filter value and automatically reset page to 1.
   * Use this for all filter changes (not page navigation).
   */
  const setFilter = useCallback(
    (updates: Partial<typeof params>) => {
      setParams({ ...updates, page: 1 });
    },
    [setParams]
  );

  return { params, setParams, setFilter, data, loading, error };
}
