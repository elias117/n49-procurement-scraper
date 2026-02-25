"use client";

import { Button } from "@/components/ui/button";
import {
  ChevronFirst,
  ChevronLast,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

/**
 * Pagination controls with first/prev/page-window/next/last buttons.
 * Shows a window of 5 page numbers centered around the current page.
 */
export function Pagination({ page, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null;

  // Compute the window of page numbers to display (up to 5)
  const windowSize = 5;
  let start = Math.max(1, page - Math.floor(windowSize / 2));
  const end = Math.min(totalPages, start + windowSize - 1);
  // Adjust start if we hit the end
  start = Math.max(1, end - windowSize + 1);

  const pageNumbers: number[] = [];
  for (let i = start; i <= end; i++) {
    pageNumbers.push(i);
  }

  const isFirst = page === 1;
  const isLast = page === totalPages;

  return (
    <div className="flex items-center justify-center gap-1 py-4">
      <Button
        variant="outline"
        size="icon-sm"
        disabled={isFirst}
        onClick={() => onPageChange(1)}
        aria-label="First page"
      >
        <ChevronFirst className="h-4 w-4" />
      </Button>
      <Button
        variant="outline"
        size="icon-sm"
        disabled={isFirst}
        onClick={() => onPageChange(page - 1)}
        aria-label="Previous page"
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>

      {pageNumbers.map((p) => (
        <Button
          key={p}
          variant={p === page ? "default" : "outline"}
          size="sm"
          onClick={() => onPageChange(p)}
          className="min-w-8"
        >
          {p}
        </Button>
      ))}

      <Button
        variant="outline"
        size="icon-sm"
        disabled={isLast}
        onClick={() => onPageChange(page + 1)}
        aria-label="Next page"
      >
        <ChevronRight className="h-4 w-4" />
      </Button>
      <Button
        variant="outline"
        size="icon-sm"
        disabled={isLast}
        onClick={() => onPageChange(totalPages)}
        aria-label="Last page"
      >
        <ChevronLast className="h-4 w-4" />
      </Button>

      <span className="ml-2 text-xs text-muted-foreground">
        Page {page} of {totalPages}
      </span>
    </div>
  );
}
