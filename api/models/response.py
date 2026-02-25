"""Search response models."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ListingResult(BaseModel):
    id: str
    title: str
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
    provinces: list[FacetValue] = []
    portals: list[FacetValue] = []


class SearchResponse(BaseModel):
    results: list[ListingResult] = []
    total_count: int = 0
    page: int = 1
    page_size: int = 25
    total_pages: int = 0
    facets: FacetCounts = FacetCounts()
