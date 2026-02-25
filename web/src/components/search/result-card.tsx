"use client";

import { Badge } from "@/components/ui/badge";
import { formatDate, formatCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ListingResult } from "@/types/search";

interface ResultCardProps {
  listing: ListingResult;
  onClick?: () => void;
  isNew?: boolean;
}

/**
 * Decision-dense result card showing all available fields from the search result.
 * Missing values are always shown explicitly -- never blank.
 *
 * Fields from search API: title, source_portal_name, closing_date, posting_date,
 * province, value_min, value_max, snippet.
 *
 * Note: status and classification_codes are only available in the detail endpoint
 * and will be shown in the detail side panel (Plan 4-03).
 */
export function ResultCard({ listing, onClick, isNew }: ResultCardProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.();
        }
      }}
      className={cn(
        "rounded-lg border bg-card p-4 transition-shadow hover:shadow-md cursor-pointer",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
    >
      {/* Title row with New badge */}
      <div className="flex items-start gap-2 mb-2">
        <h3 className="text-sm font-semibold text-foreground leading-snug flex-1">
          {listing.title}
        </h3>
        {isNew && (
          <Badge className="shrink-0 bg-emerald-600 text-white text-[10px] px-1.5">
            New
          </Badge>
        )}
      </div>

      {/* Metadata row */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground mb-2">
        <span className="font-medium text-foreground/80">
          {listing.source_portal_name}
        </span>
        <span className="text-border">|</span>
        <span>
          Province: {listing.province || "Not specified"}
        </span>
        <span className="text-border">|</span>
        <span>
          Posted: {formatDate(listing.posting_date)}
        </span>
        <span className="text-border">|</span>
        <span>
          Closes: {formatDate(listing.closing_date)}
        </span>
      </div>

      {/* Value */}
      <div className="text-xs mb-2">
        <span className="text-muted-foreground">Value: </span>
        <span className="font-medium text-foreground">
          {formatCurrency(listing.value_min, listing.value_max)}
        </span>
      </div>

      {/* Snippet with keyword highlights */}
      {listing.snippet && (
        <p
          className="text-xs text-muted-foreground leading-relaxed line-clamp-3 [&_mark]:bg-yellow-200 [&_mark]:text-foreground [&_mark]:rounded-sm [&_mark]:px-0.5"
          dangerouslySetInnerHTML={{ __html: listing.snippet }}
        />
      )}
    </div>
  );
}
