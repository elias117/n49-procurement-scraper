"use client";

import { useEffect, useRef, useState } from "react";
import { API_PUBLIC } from "@/lib/api";
import type { ListingDetail } from "@/types/listing";

/**
 * Fetch listing detail by ID with AbortController cleanup.
 * Clears listing data when listingId becomes null.
 */
export function useListingDetail(listingId: string | null) {
  const [listing, setListing] = useState<ListingDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Cancel any in-flight request
    if (abortRef.current) {
      abortRef.current.abort();
    }

    // Clear data when no listing is selected
    if (!listingId) {
      setListing(null);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;

    async function fetchDetail() {
      setLoading(true);
      setError(null);

      try {
        const res = await fetch(
          `${API_PUBLIC}/listings/${listingId}`,
          { signal: controller.signal }
        );

        if (!res.ok) {
          throw new Error(
            `Failed to load listing: ${res.status} ${res.statusText}`
          );
        }

        const data: ListingDetail = await res.json();
        setListing(data);
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
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

    fetchDetail();

    return () => {
      controller.abort();
    };
  }, [listingId]);

  return { listing, loading, error };
}
