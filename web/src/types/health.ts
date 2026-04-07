/**
 * Types for the scraper health dashboard.
 */

export interface PortalHealth {
  portal_id: string;
  name: string;
  url: string;
  level: "federal" | "provincial" | "municipal";
  province: string | null;
  enabled: boolean;
  recent_failures: number | null;
  recent_total: number | null;
  last_success_at: string | null;
  last_run_at: string | null;
  latest_completed_listings_found: number | null;
  historical_nonzero_runs: number;
  zero_result_regression: boolean;
  last_run_status: string | null;
  listings_found: number | null;
  listings_new: number | null;
  listings_updated: number | null;
  duration_seconds: number | null;
  error_message: string | null;
  total_listings: number;
}

export interface FreshnessData {
  last_updated: string | null;
}
