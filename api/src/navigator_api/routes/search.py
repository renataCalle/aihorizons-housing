from fastapi import APIRouter, Query

from navigator_api.models import LookupResponse
from navigator_api.routes.deps import Source
from navigator_api.search.lookup import lookup

router = APIRouter(tags=["search"])


@router.get("/lookup")
def lookup_parcels(source: Source, q: str = Query(max_length=200)) -> LookupResponse:
    """Parcels matching a county ID (dashed, compact or partial), block-lot or address."""
    return lookup(source.summaries(), q)
