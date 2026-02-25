/**
 * nuqs parser definitions for all 16 search parameters.
 * Maps 1-to-1 with the FastAPI /search endpoint query parameters.
 */
import {
  parseAsArrayOf,
  parseAsBoolean,
  parseAsFloat,
  parseAsInteger,
  parseAsIsoDateTime,
  parseAsString,
  parseAsStringLiteral,
} from "nuqs";

export const searchParamsParsers = {
  q: parseAsString.withDefault(""),
  mode: parseAsStringLiteral(["hybrid", "exact"] as const).withDefault(
    "hybrid"
  ),
  page: parseAsInteger.withDefault(1),
  page_size: parseAsInteger.withDefault(25),
  sort_by: parseAsStringLiteral([
    "relevance",
    "posting_date",
    "closing_date",
    "value",
  ] as const).withDefault("relevance"),
  sort_order: parseAsStringLiteral(["asc", "desc"] as const).withDefault(
    "desc"
  ),
  include_closed: parseAsBoolean.withDefault(false),
  regions: parseAsArrayOf(parseAsString).withDefault([]),
  portals: parseAsArrayOf(parseAsString).withDefault([]),
  closing_date_from: parseAsIsoDateTime,
  closing_date_to: parseAsIsoDateTime,
  posting_date_from: parseAsIsoDateTime,
  posting_date_to: parseAsIsoDateTime,
  value_min: parseAsFloat,
  value_max: parseAsFloat,
  classification_codes: parseAsArrayOf(parseAsString).withDefault([]),
};
