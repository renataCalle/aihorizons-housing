from fastapi import APIRouter

from navigator_api.models import Examples, Health
from navigator_api.routes.deps import Source

router = APIRouter(tags=["health"])


@router.get("/health")
def health(source: Source) -> Health:
    return Health(
        site_source=source.name,
        illustrative=source.illustrative(),
        parcels=len(source.summaries()),
        versions=source.versions(),
    )


@router.get("/examples")
def examples(source: Source) -> Examples:
    """Example searches for the landing page, from the data being served."""
    return source.examples()
