"use client";

import { Badge } from "@/components/ui/badge";
import type { PortalHealth } from "@/types/health";

export type PortalStatus = "healthy" | "warning" | "stale" | "unknown" | "running";

/**
 * Determine the health status of a portal based on staleness thresholds.
 *
 * LOCKED thresholds:
 *  - HEALTHY (green): Last run succeeded AND <3 recent failures AND last success within 7 days
 *  - WARNING (amber): 3+ failures in last 5 runs (recent_failures >= 3)
 *  - STALE/ERROR (red): 7+ days since last success
 *  - UNKNOWN (gray): No runs recorded (last_run_status is null)
 *  - RUNNING (blue): last_run_status is "running"
 */
export function getPortalStatus(portal: PortalHealth): PortalStatus {
  // No runs recorded
  if (!portal.last_run_status) {
    return "unknown";
  }

  // Currently running
  if (portal.last_run_status === "running") {
    return "running";
  }

  // Check staleness: 7+ days since last success
  if (portal.last_success_at) {
    const daysSinceSuccess = Math.floor(
      (Date.now() - new Date(portal.last_success_at).getTime()) /
        (1000 * 60 * 60 * 24)
    );
    if (daysSinceSuccess >= 7) {
      return "stale";
    }
  } else {
    // Has runs but never succeeded -- treat as stale
    return "stale";
  }

  // Check warning: 3+ failures in recent runs
  if ((portal.recent_failures ?? 0) >= 3) {
    return "warning";
  }

  return "healthy";
}

const statusConfig: Record<
  PortalStatus,
  { label: string; className: string }
> = {
  healthy: {
    label: "Healthy",
    className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200",
  },
  warning: {
    label: "Warning",
    className: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  },
  stale: {
    label: "Stale",
    className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  },
  unknown: {
    label: "No data",
    className: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  },
  running: {
    label: "Running",
    className: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  },
};

/** Sort priority: lower = higher in table */
export const STATUS_SORT_ORDER: Record<PortalStatus, number> = {
  stale: 0,
  warning: 1,
  running: 2,
  unknown: 3,
  healthy: 4,
};

interface StatusBadgeProps {
  lastStatus: string | null;
  recentFailures: number;
  recentTotal: number;
  lastSuccessAt: string | null;
}

export function StatusBadge({
  lastStatus,
  recentFailures,
  recentTotal,
  lastSuccessAt,
}: StatusBadgeProps) {
  const portal = {
    last_run_status: lastStatus,
    recent_failures: recentFailures,
    recent_total: recentTotal,
    last_success_at: lastSuccessAt,
  } as PortalHealth;

  const status = getPortalStatus(portal);
  const config = statusConfig[status];

  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  );
}
