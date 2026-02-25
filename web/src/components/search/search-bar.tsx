"use client";

import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  query: string;
  mode: "hybrid" | "exact";
  onQueryChange: (q: string) => void;
  onModeChange: (mode: "hybrid" | "exact") => void;
}

/**
 * Debounced search bar with mode toggle (hybrid/exact).
 * Local input state syncs to URL params after 300ms debounce.
 */
export function SearchBar({
  query,
  mode,
  onQueryChange,
  onModeChange,
}: SearchBarProps) {
  const [localValue, setLocalValue] = useState(query);
  const isInitialMount = useRef(true);

  // Keep local value in sync when URL changes externally (e.g., back/forward)
  useEffect(() => {
    setLocalValue(query);
  }, [query]);

  // Debounce: sync local input to URL params after 300ms
  useEffect(() => {
    // Skip the initial mount to avoid an unnecessary URL update
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    const timer = setTimeout(() => {
      if (localValue !== query) {
        onQueryChange(localValue);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [localValue, query, onQueryChange]);

  function handleClear() {
    setLocalValue("");
    onQueryChange("");
  }

  return (
    <div className="flex items-center gap-2 w-full">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search procurement listings..."
          value={localValue}
          onChange={(e) => setLocalValue(e.target.value)}
          className="pl-10 pr-10 h-10 rounded-lg"
        />
        {localValue && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="flex items-center rounded-lg border bg-background">
        <Button
          type="button"
          variant={mode === "hybrid" ? "default" : "ghost"}
          size="sm"
          className={cn("rounded-r-none text-xs h-10")}
          onClick={() => onModeChange("hybrid")}
        >
          Hybrid
        </Button>
        <Button
          type="button"
          variant={mode === "exact" ? "default" : "ghost"}
          size="sm"
          className={cn("rounded-l-none text-xs h-10")}
          onClick={() => onModeChange("exact")}
        >
          Exact
        </Button>
      </div>
    </div>
  );
}
