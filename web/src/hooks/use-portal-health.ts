"use client";

import { useEffect, useState, useCallback } from "react";
import type { PortalHealth } from "@/types/health";
import { API_PUBLIC } from "@/lib/api";

/**
 * Hook to fetch and auto-refresh portal health data.
 * Fetches from /api/health/portals on mount and every 60 seconds.
 */
export function usePortalHealth() {
  const [portals, setPortals] = useState<PortalHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_PUBLIC}/health/portals`);
      if (!res.ok) {
        throw new Error(`Failed to fetch portal health: ${res.status}`);
      }
      const data: PortalHealth[] = await res.json();
      setPortals(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();

    const interval = setInterval(fetchHealth, 60_000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  return { portals, loading, error };
}
