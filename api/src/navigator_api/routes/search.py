from fastapi import APIRouter, Query

from navigator_api.models import (
    AreaSummary,
    LookupResponse,
    Neighborhood,
    ParseRequest,
    ParseResult,
    SearchFilters,
    SearchResponse,
)
from navigator_api.routes.deps import Source
from navigator_api.search.area import summarize_area, with_extras
from navigator_api.search.lookup import lookup
from navigator_api.search.parse import parse
from navigator_api.search.query import search
from navigator_api.search.vocabulary import NEIGHBORHOODS

router = APIRouter(tags=["search"])


@router.get("/lookup")
def lookup_parcels(source: Source, q: str = Query(max_length=200)) -> LookupResponse:
    """Parcels matching a county ID (dashed, compact or partial), block-lot or address."""
    return lookup(source.summaries(), q)


@router.post("/search")
def search_parcels(filters: SearchFilters, source: Source) -> SearchResponse:
    """Candidates that pass every filter, ranked; near misses and a suggestion when empty."""
    return search(source.summaries(), filters, source.map_features(), source.program_rows)


@router.post("/search/summary")
def search_summary(filters: SearchFilters, source: Source) -> AreaSummary:
    """The same search at a glance: lots per band, what holds them back, near misses."""
    response = search(
        source.summaries(), with_extras(filters), source.map_features(), source.program_rows
    )
    return summarize_area(response, len(response.near_misses), source.analysis)


@router.post("/search/parse")
def parse_text(request: ParseRequest) -> ParseResult:
    """Plain-language description to search filters. It never searches, scores or ranks."""
    return parse(request.text, request.current_filters)


@router.get("/neighborhoods")
def neighborhoods(source: Source) -> list[Neighborhood]:
    """The city's 90 neighborhoods, with how many candidates each has in the data."""
    counts: dict[str, int] = {}
    for s in source.summaries():
        if s.candidate and s.neighborhood:
            counts[s.neighborhood] = counts.get(s.neighborhood, 0) + 1
    return [Neighborhood(name=n, candidates=counts.get(n, 0)) for n in NEIGHBORHOODS]
