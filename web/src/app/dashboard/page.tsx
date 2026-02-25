"use client";

import { Suspense, useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useSearch } from "@/hooks/use-search";
import { useListingDetail } from "@/hooks/use-listing-detail";
import { SearchBar } from "@/components/search/search-bar";
import { FilterSidebar } from "@/components/search/filter-sidebar";
import { ResultsList } from "@/components/search/results-list";
import { Pagination } from "@/components/search/pagination";
import { SortControls } from "@/components/search/sort-controls";
import { ListingDetailSheet } from "@/components/search/listing-detail";
import { Skeleton } from "@/components/ui/skeleton";
import { API_PUBLIC } from "@/lib/api";
import type { ListingResult } from "@/types/search";

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
  const { data: session } = useSession();

  // Listing detail Sheet state
  const [selectedListingId, setSelectedListingId] = useState<string | null>(null);
  const { listing: detailListing, loading: detailLoading } =
    useListingDetail(selectedListingId);

  // "New" badge: store the PREVIOUS last_visited_at before updating
  const [lastVisitedAt, setLastVisitedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!session?.user?.id) return;

    const userId = session.user.id;

    async function readThenUpdateLastVisit() {
      try {
        // Step 1: READ the previous last_visited_at value
        const getRes = await fetch(`${API_PUBLIC}/users/${userId}/last-visit`);
        if (getRes.ok) {
          const body = await getRes.json();
          // Store the PREVIOUS value for "New" badge comparison
          setLastVisitedAt(body.last_visited_at ?? null);
        }

        // Step 2: UPDATE last_visited_at to NOW (for next visit)
        await fetch(`${API_PUBLIC}/users/${userId}/last-visit`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
        });
      } catch {
        // Non-critical: badges just won't show if this fails
      }
    }

    readThenUpdateLastVisit();
  }, [session?.user?.id]);

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
