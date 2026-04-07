/**
 * Types for the listing detail view.
 */

export interface ContactInfo {
  name?: string;
  email?: string;
  phone?: string;
  title?: string;
}

export interface Document {
  name: string;
  url: string;
  type?: string;
  date?: string;
}

export interface ClassificationCode {
  code: string;
  system?: string;
  description?: string;
}

export interface ListingDetail {
  id: string;
  source_portal: string;
  source_listing_id: string | null;
  reference_number: string | null;
  title: string;
  description: string | null;
  status: string;
  language: string | null;
  posting_date: string | null;
  closing_date: string | null;
  amended_date: string | null;
  province: string | null;
  raw_location: string | null;
  classification_codes: (ClassificationCode | string)[];
  value_min: number | null;
  value_max: number | null;
  contact_info: ContactInfo | null;
  documents: Document[];
  revision: number;
  source_url: string | null;
  last_scraped_at: string;
  created_at: string;
  updated_at: string;
  source_portal_name: string;
  portal_url: string;
}
