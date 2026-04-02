"""Search response models."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ListingResult(BaseModel):
    id: str
    title: str
    reference_number: Optional[str] = None
    source_portal_name: str
    closing_date: Optional[datetime] = None
    province: Optional[str] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    snippet: str
    posting_date: Optional[datetime] = None


class FacetValue(BaseModel):
    value: str
    count: int


class FacetCounts(BaseModel):
    provinces: list[FacetValue] = Field(default_factory=list)
    portals: list[FacetValue] = Field(default_factory=list)


class SearchResponse(BaseModel):
    results: list[ListingResult] = Field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 25
    total_pages: int = 0
    facets: FacetCounts = Field(default_factory=FacetCounts)
