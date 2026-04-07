/**
 * Types matching the FastAPI search API response models.
 */

export interface ListingResult {
  id: string;
  title: string;
  reference_number?: string | null;
  source_listing_id?: string | null;
  source_portal_name: string;
  closing_date: string | null;
  province: string | null;
  value_min: number | null;
  value_max: number | null;
  snippet: string;
  posting_date: string | null;
}

export interface FacetValue {
  value: string;
  count: number;
}

export interface FacetCounts {
  provinces: FacetValue[];
  portals: FacetValue[];
}

export interface SearchResponse {
  results: ListingResult[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
  facets: FacetCounts;
}
