"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  StatusBadge,
  getPortalStatus,
  STATUS_SORT_ORDER,
} from "@/components/health/status-badge";
import { formatDate } from "@/lib/format";
import type { PortalHealth } from "@/types/health";
import {
  CheckCircle,
  XCircle,
  Loader2,
  ExternalLink,
  AlertTriangle,
} from "lucide-react";

interface PortalTableProps {
  portals: PortalHealth[];
  loading: boolean;
}

function StatusIcon({ status }: { status: string | null }) {
  if (status === "completed") {
    return <CheckCircle className="h-4 w-4 text-emerald-600" />;
  }
  if (status === "failed") {
    return <XCircle className="h-4 w-4 text-red-600" />;
  }
  if (status === "running") {
    return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />;
  }
  return <span className="text-muted-foreground">-</span>;
}

const levelStyles: Record<string, string> = {
  federal: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  provincial: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  municipal: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
};

function sortPortals(portals: PortalHealth[]): PortalHealth[] {
  return [...portals].sort((a, b) => {
    const statusA = STATUS_SORT_ORDER[getPortalStatus(a)];
    const statusB = STATUS_SORT_ORDER[getPortalStatus(b)];
    if (statusA !== statusB) return statusA - statusB;
    return a.name.localeCompare(b.name);
  });
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 5 }).map((_, i) => (
        <TableRow key={i}>
          {Array.from({ length: 11 }).map((_, j) => (
            <TableCell key={j}>
              <Skeleton className="h-5 w-full" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}

export function PortalTable({ portals, loading }: PortalTableProps) {
  const sorted = sortPortals(portals);

  const statuses = portals.map(getPortalStatus);
  const healthyCount = statuses.filter((status) => status === "healthy").length;
  const warningCount = statuses.filter((status) => status === "warning").length;
  const staleCount = statuses.filter((status) => status === "stale").length;
  const regressionCount = statuses.filter(
    (status) => status === "regression"
  ).length;

  return (
    <TooltipProvider>
      <div className="space-y-4">
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span>{portals.length} portals total</span>
          <span className="text-emerald-600">{healthyCount} healthy</span>
          <span className="text-amber-600">{warningCount} warnings</span>
          <span className="text-red-700">{regressionCount} regressions</span>
          <span className="text-red-600">{staleCount} stale</span>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Status</TableHead>
              <TableHead>Regression</TableHead>
              <TableHead>Portal Name</TableHead>
              <TableHead>Level</TableHead>
              <TableHead>Province</TableHead>
              <TableHead>Last Run</TableHead>
              <TableHead>Last Status</TableHead>
              <TableHead className="text-right">Listings</TableHead>
              <TableHead>Recent</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Error</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <SkeletonRows />
            ) : sorted.length === 0 ? (
              <TableRow>
                <TableCell colSpan={11} className="text-center py-8 text-muted-foreground">
                  No portals found.
                </TableCell>
              </TableRow>
            ) : (
              sorted.map((portal) => (
                <TableRow key={portal.portal_id}>
                  <TableCell>
                    <StatusBadge
                      lastStatus={portal.last_run_status}
                      recentFailures={portal.recent_failures ?? 0}
                      recentTotal={portal.recent_total ?? 0}
                      lastSuccessAt={portal.last_success_at}
                      zeroResultRegression={portal.zero_result_regression}
                    />
                  </TableCell>
                  <TableCell>
                    {portal.zero_result_regression ? (
                      <div className="flex items-center gap-1.5 text-red-700 dark:text-red-300">
                        <AlertTriangle className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-medium">
                          Latest completed run found 0 after{" "}
                          {portal.historical_nonzero_runs} non-zero runs
                        </span>
                      </div>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <a
                      href={portal.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-medium hover:underline"
                    >
                      {portal.name}
                      <ExternalLink className="h-3 w-3 text-muted-foreground" />
                    </a>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={levelStyles[portal.level] ?? ""}
                    >
                      {portal.level}
                    </Badge>
                  </TableCell>
                  <TableCell>{portal.province ?? "-"}</TableCell>
                  <TableCell>
                    {portal.last_run_at
                      ? formatDate(portal.last_run_at)
                      : "Never"}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <StatusIcon status={portal.last_run_status} />
                      <span className="text-sm">
                        {portal.last_run_status ?? "-"}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {portal.total_listings.toLocaleString()}
                  </TableCell>
                  <TableCell>
                    {portal.recent_total
                      ? `Failed ${portal.recent_failures ?? 0} of ${portal.recent_total} runs`
                      : "-"}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {portal.duration_seconds != null
                      ? `${Math.round(portal.duration_seconds)}s`
                      : "-"}
                  </TableCell>
                  <TableCell className="max-w-[200px]">
                    {portal.error_message ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="truncate block text-sm text-red-600 cursor-help">
                            {portal.error_message.length > 50
                              ? `${portal.error_message.slice(0, 50)}...`
                              : portal.error_message}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent
                          side="left"
                          className="max-w-sm whitespace-pre-wrap"
                        >
                          {portal.error_message}
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </TooltipProvider>
  );
}
