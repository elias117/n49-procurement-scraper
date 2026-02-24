"""
Pydantic models for the scraper pipeline.

These models match the PostgreSQL schema defined in db/migrations/001_initial_schema.sql.
ProcurementListing is the instructor extraction target (LLM output).
ListingRecord is the DB-ready representation (post-validation).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# ProcurementListing — instructor extraction target
# ---------------------------------------------------------------------------
class ProcurementListing(BaseModel):
    """A single procurement listing extracted from a portal page by the LLM."""

    title: str = Field(
        description="The title of the procurement opportunity. Required."
    )
    description: Optional[str] = Field(
        default=None,
        description="Full description of the procurement opportunity.",
    )
    reference_number: Optional[str] = Field(
        default=None,
        description="The official reference or solicitation number.",
    )
    posting_date: Optional[str] = Field(
        default=None,
        description="Date the listing was posted, in ISO format YYYY-MM-DD.",
    )
    closing_date: Optional[str] = Field(
        default=None,
        description=(
            "Deadline for submissions in ISO format YYYY-MM-DD. "
            "Extract only if explicitly stated in the text. "
            "Return null if not clearly present. NEVER guess or infer."
        ),
    )
    status: Optional[str] = Field(
        default=None,
        description=(
            "Current status of the listing: open, closed, cancelled, or awarded."
        ),
    )
    value_min: Optional[float] = Field(
        default=None,
        description=(
            "Minimum estimated contract value in CAD. "
            "Extract only if explicitly stated in the text. "
            "Return null if not clearly present. NEVER guess or infer."
        ),
    )
    value_max: Optional[float] = Field(
        default=None,
        description=(
            "Maximum estimated contract value in CAD. "
            "Extract only if explicitly stated in the text. "
            "Return null if not clearly present. NEVER guess or infer."
        ),
    )
    contact_name: Optional[str] = Field(
        default=None,
        description="Name of the procurement contact person.",
    )
    contact_email: Optional[str] = Field(
        default=None,
        description="Email address of the procurement contact.",
    )
    contact_phone: Optional[str] = Field(
        default=None,
        description="Phone number of the procurement contact.",
    )
    source_url: Optional[str] = Field(
        default=None,
        description="URL of the original listing page on the source portal.",
    )
    source_listing_id: Optional[str] = Field(
        default=None,
        description="Unique identifier for this listing on the source portal.",
    )
    classification_codes: Optional[list[dict]] = Field(
        default=None,
        description=(
            "Classification codes as a list of objects with keys: system, code, description. "
            "Systems include NAICS, UNSPSC, GSIN. "
            "Extract only if explicitly stated in the text. "
            "Return null if not clearly present. NEVER guess or infer."
        ),
    )
    province: Optional[str] = Field(
        default=None,
        description="Canadian province or territory for the procurement.",
    )
    raw_location: Optional[str] = Field(
        default=None,
        description="Raw location text as it appears in the listing.",
    )
    documents: Optional[list[dict]] = Field(
        default=None,
        description=(
            "Attached documents as a list of objects with keys: name, type, url, date."
        ),
    )


# ---------------------------------------------------------------------------
# ExtractionResult — wraps multiple listings from a single page
# ---------------------------------------------------------------------------
class ExtractionResult(BaseModel):
    """Result of extracting procurement listings from a portal page."""

    listings: list[ProcurementListing] = Field(
        default_factory=list,
        description="List of procurement listings found on the page.",
    )


# ---------------------------------------------------------------------------
# ListingRecord — DB-ready, post-validation
# ---------------------------------------------------------------------------
class ListingRecord(BaseModel):
    """
    Database-ready listing record.

    Combines extraction data with portal metadata, embeddings, and
    computed fields. Maps directly to the listings table columns.

    NOTE: Does NOT have contact_name/contact_email/contact_phone.
    Those exist only on ProcurementListing for LLM extraction clarity.
    Use to_listing_record() to consolidate them into contact_info JSONB.
    """

    title: str
    description: Optional[str] = None
    reference_number: Optional[str] = None
    posting_date: Optional[str] = None
    closing_date: Optional[str] = None
    status: Optional[str] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    source_url: Optional[str] = None
    source_listing_id: Optional[str] = None
    classification_codes: Optional[list[dict]] = None
    province: Optional[str] = None
    raw_location: Optional[str] = None
    documents: Optional[list[dict]] = None

    # Portal and metadata fields
    source_portal: str = Field(
        description="UUID of the source portal (portals.id)."
    )
    contact_info: Optional[dict] = Field(
        default=None,
        description="Consolidated contact info JSONB: {name, email, phone}.",
    )
    amended_date: Optional[str] = Field(
        default=None,
        description="Date the listing was last amended, ISO format YYYY-MM-DD.",
    )
    embedding: Optional[list[float]] = Field(
        default=None,
        description="Embedding vector from text-embedding-3-small (1536 dims).",
    )
    embedding_model: Optional[str] = Field(
        default=None,
        description="Name of the embedding model used.",
    )
    language: Optional[str] = Field(
        default=None,
        description="Language of the listing: en, fr, or both.",
    )
    completeness_score: float = Field(
        default=0.0,
        description="Score 0-1 indicating how many fields are populated.",
    )


# ---------------------------------------------------------------------------
# Factory function: ProcurementListing -> ListingRecord
# ---------------------------------------------------------------------------
def to_listing_record(
    extraction: ProcurementListing,
    portal_id: str,
    language: str,
) -> ListingRecord:
    """
    Convert a ProcurementListing (LLM output) to a ListingRecord (DB-ready).

    Consolidates contact_name/contact_email/contact_phone into contact_info
    JSONB dict, omitting keys with None values.
    """
    # Build contact_info from separate contact fields
    contact_info = {}
    if extraction.contact_name is not None:
        contact_info["name"] = extraction.contact_name
    if extraction.contact_email is not None:
        contact_info["email"] = extraction.contact_email
    if extraction.contact_phone is not None:
        contact_info["phone"] = extraction.contact_phone

    return ListingRecord(
        title=extraction.title,
        description=extraction.description,
        reference_number=extraction.reference_number,
        posting_date=extraction.posting_date,
        closing_date=extraction.closing_date,
        status=extraction.status,
        value_min=extraction.value_min,
        value_max=extraction.value_max,
        source_url=extraction.source_url,
        source_listing_id=extraction.source_listing_id,
        classification_codes=extraction.classification_codes,
        province=extraction.province,
        raw_location=extraction.raw_location,
        documents=extraction.documents,
        source_portal=portal_id,
        contact_info=contact_info if contact_info else None,
        language=language,
    )


# ---------------------------------------------------------------------------
# PortalRecord — maps to portals table
# ---------------------------------------------------------------------------
class PortalRecord(BaseModel):
    """Represents a row from the portals table."""

    id: str
    name: str
    url: str
    level: str
    province: Optional[str] = None
    language: str
    requires_login: bool
    enabled: bool


# ---------------------------------------------------------------------------
# ScrapeRunRecord — maps to scrape_runs table
# ---------------------------------------------------------------------------
class ScrapeRunRecord(BaseModel):
    """Represents a row from the scrape_runs table."""

    id: Optional[str] = None
    portal_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"
    listings_found: int = 0
    listings_new: int = 0
    listings_updated: int = 0
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
