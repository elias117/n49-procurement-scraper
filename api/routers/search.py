"""Search endpoint (stub -- implemented in Plan 3-02)."""
from fastapi import APIRouter
from api.models.response import SearchResponse

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search_listings():
    """Search procurement listings. Stub -- returns empty results."""
    return SearchResponse()
