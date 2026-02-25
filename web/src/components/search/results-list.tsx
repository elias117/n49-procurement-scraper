"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { ResultCard } from "@/components/search/result-card";
import type { ListingResult } from "@/types/search";

interface ResultsListProps {
  results: ListingResult[];
  loading: boolean;
  onSelectListing?: (listing: ListingResult) => void;
  total_count: number;
  lastVisitedAt?: string | null;
}

/**
 * Renders the list of search result cards with loading, empty,
 * and results states.
 */
export function ResultsList({
  results,
  loading,
  onSelectListing,
  total_count,
  lastVisitedAt,
}: ResultsListProps) {
  if (loading) {
    return (
      <div className="space-y-3">
        <div className="h-5 w-32">
          <Skeleton className="h-full w-full" />
        </div>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card p-4 space-y-3">
            <Skeleton className="h-5 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-12 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <p className="text-muted-foreground">
          No listings found. Try adjusting your filters.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {total_count.toLocaleString()} {total_count === 1 ? "result" : "results"} found
      </p>
      {results.map((listing) => {
        const isNew =
          lastVisitedAt && listing.posting_date
            ? new Date(listing.posting_date) > new Date(lastVisitedAt)
            : false;

        return (
          <ResultCard
            key={listing.id}
            listing={listing}
            onClick={() => onSelectListing?.(listing)}
            isNew={isNew}
          />
        );
      })}
    </div>
  );
}
