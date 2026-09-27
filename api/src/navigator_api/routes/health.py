from fastapi import APIRouter

from navigator_api.models import Examples, Health
from navigator_api.routes.deps import AI, Source

router = APIRouter(tags=["health"])


@router.get("/health")
def health(source: Source, ai: AI) -> Health:
    return Health(
        site_source=source.name,
        illustrative=source.illustrative(),
        parcels=len(source.summaries()),
        ai_search=ai is not None,
        versions=source.versions(),
    )


@router.get("/examples")
def examples(source: Source) -> Examples:
    """Example searches for the landing page, from the data being served."""
    return source.examples()
