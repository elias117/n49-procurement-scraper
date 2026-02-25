/**
 * Formatting utilities for dates, currency, and relative time.
 */
import { formatDistanceToNow } from "date-fns";

/**
 * Format a date string or Date to a human-readable format.
 * Returns "Not specified" for null/undefined values.
 *
 * Uses UTC timezone to prevent off-by-one day display: procurement dates
 * are date-only values stored as midnight UTC, so local timezone conversion
 * would shift them back a day for users west of UTC.
 */
export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return "Not specified";
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return "Not specified";
  return d.toLocaleDateString("en-CA", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/**
 * Format a contract value range for display.
 * Handles missing values with explicit "Value not disclosed" messaging.
 */
export function formatCurrency(
  min?: number | null,
  max?: number | null
): string {
  if (min == null && max == null) return "Value not disclosed";

  const fmt = (n: number) =>
    new Intl.NumberFormat("en-CA", {
      style: "currency",
      currency: "CAD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(n);

  if (min != null && max != null) return `${fmt(min)} - ${fmt(max)}`;
  if (min != null) return `${fmt(min)}+`;
  return `Up to ${fmt(max!)}`;
}

/**
 * Format a date as a relative time string (e.g., "3 hours ago").
 */
export function formatRelativeTime(
  date: string | Date | null | undefined
): string {
  if (!date) return "Unknown";
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return "Unknown";
  return formatDistanceToNow(d, { addSuffix: true });
}
