from fastapi import APIRouter, Query

from navigator_api.models import LookupResponse, SearchFilters, SearchResponse
from navigator_api.routes.deps import Source
from navigator_api.search.lookup import lookup
from navigator_api.search.query import search

router = APIRouter(tags=["search"])


@router.get("/lookup")
def lookup_parcels(source: Source, q: str = Query(max_length=200)) -> LookupResponse:
    """Parcels matching a county ID (dashed, compact or partial), block-lot or address."""
    return lookup(source.summaries(), q)


@router.post("/search")
def search_parcels(filters: SearchFilters, source: Source) -> SearchResponse:
    """Candidates that pass every filter, ranked; near misses and a suggestion when empty."""
    return search(source.summaries(), filters, source.map_features())
