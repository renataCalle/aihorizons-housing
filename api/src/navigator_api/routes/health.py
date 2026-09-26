from fastapi import APIRouter

from navigator_api.models import Health
from navigator_api.routes.deps import Source

router = APIRouter(tags=["health"])


@router.get("/health")
def health(source: Source) -> Health:
    return Health(
        site_source=source.name, illustrative=source.illustrative, versions=source.versions()
    )
