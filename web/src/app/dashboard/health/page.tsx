"use client";

import { usePortalHealth } from "@/hooks/use-portal-health";
import { PortalTable } from "@/components/health/portal-table";

export default function HealthPage() {
  const { portals, loading, error } = usePortalHealth();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Scraper Health
        </h1>
        <p className="text-sm text-muted-foreground">
          Monitor portal scraper status and reliability.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          Failed to load portal health data: {error}
        </div>
      )}

      <PortalTable portals={portals} loading={loading} />
    </div>
  );
}
