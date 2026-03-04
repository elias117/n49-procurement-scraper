"use client";

import { ArrowUp, ArrowDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type SortField = "relevance" | "posting_date" | "closing_date" | "value";
type SortOrder = "asc" | "desc";

interface SortControlsProps {
  sort_by: SortField;
  sort_order: SortOrder;
  onSortChange: (updates: { sort_by?: SortField; sort_order?: SortOrder }) => void;
}

const SORT_LABELS: Record<SortField, string> = {
  relevance: "Relevance",
  posting_date: "Posting Date",
  closing_date: "Closing Date",
  value: "Value",
};

/**
 * Sort field dropdown + ascending/descending toggle.
 * Resets page to 1 on any change (handled by parent via setFilter).
 */
export function SortControls({
  sort_by,
  sort_order,
  onSortChange,
}: SortControlsProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        Sort by
      </span>
      <Select
        value={sort_by}
        onValueChange={(value: SortField) => onSortChange({ sort_by: value })}
      >
        <SelectTrigger size="sm" className="w-[140px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(Object.entries(SORT_LABELS) as [SortField, string][]).map(
            ([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            )
          )}
        </SelectContent>
      </Select>
      <Button
        variant="outline"
        size="icon-sm"
        onClick={() =>
          onSortChange({ sort_order: sort_order === "asc" ? "desc" : "asc" })
        }
        aria-label={`Sort ${sort_order === "asc" ? "descending" : "ascending"}`}
      >
        {sort_order === "asc" ? (
          <ArrowUp className="h-4 w-4" />
        ) : (
          <ArrowDown className="h-4 w-4" />
        )}
      </Button>
    </div>
  );
}
