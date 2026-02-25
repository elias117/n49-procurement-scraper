"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { API_PUBLIC } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import type { FreshnessData } from "@/types/health";

const REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes

/**
 * Compact data freshness indicator for the nav bar.
 * Fetches from /api/health/freshness on mount and every 5 minutes.
 * Shows "Updated X ago" or "No data yet" if null.
 */
export function Freshness() {
  const [freshness, setFreshness] = useState<FreshnessData | null>(null);

  useEffect(() => {
    async function fetchFreshness() {
      try {
        const res = await fetch(`${API_PUBLIC}/health/freshness`);
        if (res.ok) {
          const data: FreshnessData = await res.json();
          setFreshness(data);
        }
      } catch {
        // Silently fail -- freshness is informational only
      }
    }

    fetchFreshness();
    const interval = setInterval(fetchFreshness, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  const label = freshness?.last_updated
    ? `Updated ${formatRelativeTime(freshness.last_updated)}`
    : "No data yet";

  return (
    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <Clock className="h-3 w-3" />
      <span>{label}</span>
    </div>
  );
}
