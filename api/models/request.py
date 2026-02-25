"""Search request model with all filter parameters."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    q: str = Field(default="", description="Search query text")
    mode: str = Field(default="hybrid", pattern="^(hybrid|exact)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=50)
    sort_by: str = Field(
        default="relevance",
        pattern="^(relevance|posting_date|closing_date|value)$",
    )
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    include_closed: bool = Field(default=False)
    regions: Optional[list[str]] = None
    portals: Optional[list[str]] = None
    closing_date_from: Optional[datetime] = None
    closing_date_to: Optional[datetime] = None
    posting_date_from: Optional[datetime] = None
    posting_date_to: Optional[datetime] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    classification_codes: Optional[list[str]] = None
