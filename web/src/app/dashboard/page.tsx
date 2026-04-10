"use client";

import { Suspense, useState, useEffect, useCallback } from "react";
import { useSearch } from "@/hooks/use-search";
import { useListingDetail } from "@/hooks/use-listing-detail";
import { SearchBar } from "@/components/search/search-bar";
import { FilterSidebar } from "@/components/search/filter-sidebar";
import { ResultsList } from "@/components/search/results-list";
import { Pagination } from "@/components/search/pagination";
import { SortControls } from "@/components/search/sort-controls";
import { ListingDetailSheet } from "@/components/search/listing-detail";
import { Skeleton } from "@/components/ui/skeleton";
import type { ListingResult } from "@/types/search";

const LAST_VISITED_KEY = "procurement_last_visited_at";

/**
 * Loading fallback shown while URL search params are being read.
 */
function DashboardSkeleton() {
  return (
    <div className="flex gap-6">
      <aside className="w-64 shrink-0 space-y-4">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="h-px w-full" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-4 w-full" />
        ))}
      </aside>
      <div className="flex-1 space-y-4">
        <Skeleton className="h-10 w-full" />
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-3">
            <Skeleton className="h-5 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="h-12 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Inner search page component that uses hooks requiring Suspense.
 * Manages listing detail Sheet, "New" badge logic via last_visited_at,
 * and all search state.
 */
function DashboardContent() {
  const { params, setParams, setFilter, data, loading, error } = useSearch();

  // Listing detail Sheet state
  const [selectedListingId, setSelectedListingId] = useState<string | null>(null);
  const { listing: detailListing, loading: detailLoading } =
    useListingDetail(selectedListingId);

  // "New" badge: stored in localStorage so it persists without auth
  const [lastVisitedAt] = useState<string | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }

    try {
      return localStorage.getItem(LAST_VISITED_KEY);
    } catch {
      return null;
    }
  });

  useEffect(() => {
    try {
      // Update to NOW (for next visit)
      localStorage.setItem(LAST_VISITED_KEY, new Date().toISOString());
    } catch {
      // Non-critical: badges just won't show if localStorage is unavailable
    }
  }, []);

  const handleSelectListing = useCallback((listing: ListingResult) => {
    setSelectedListingId(listing.id);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedListingId(null);
  }, []);

  return (
    <>
      <div className="flex gap-6">
        {/* Sidebar filters -- always visible (Amazon-style) */}
        <FilterSidebar
          params={params}
          setFilter={setFilter}
          facets={data?.facets ?? null}
        />

        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Search bar + Sort controls */}
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <SearchBar
                query={params.q}
                mode={params.mode}
                onQueryChange={(q) => setFilter({ q })}
                onModeChange={(mode) => setFilter({ mode })}
              />
            </div>
            <SortControls
              sort_by={params.sort_by}
              sort_order={params.sort_order}
              onSortChange={(updates) => setFilter(updates)}
            />
          </div>

          {/* Error state */}
          {error && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
              {error}
            </div>
          )}

          {/* Results */}
          <ResultsList
            results={data?.results ?? []}
            loading={loading}
            onSelectListing={handleSelectListing}
            total_count={data?.total_count ?? 0}
            lastVisitedAt={lastVisitedAt}
          />

          {/* Pagination */}
          {data && data.total_pages > 1 && (
            <Pagination
              page={data.page}
              totalPages={data.total_pages}
              onPageChange={(page) => setParams({ page })}
            />
          )}
        </div>
      </div>

      {/* Listing detail slide-out -- results list stays visible behind */}
      <ListingDetailSheet
        listing={detailListing}
        open={selectedListingId !== null}
        onClose={handleCloseDetail}
        loading={detailLoading}
      />
    </>
  );
}

/**
 * Main search page -- the primary interface for the BD team.
 * Wrapped in Suspense because nuqs useQueryStates reads URL search params.
 */
export default function DashboardPage() {
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <DashboardContent />
    </Suspense>
  );
}
