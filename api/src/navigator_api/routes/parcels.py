from fastapi import APIRouter, HTTPException

from navigator_api.models import ProductType, SiteAnalysis
from navigator_api.parcel_ids import normalize_county_id
from navigator_api.routes.deps import Source

router = APIRouter(tags=["parcels"])


@router.get("/parcels/{parcel_id}/analysis")
def parcel_analysis(
    parcel_id: str,
    source: Source,
    product: ProductType | None = None,
    units: int | None = None,
) -> SiteAnalysis:
    """Screening analysis for one parcel, by county parcel ID (dashed or compact).

    `product` and `units` are passed to the engine once it exists; the mock ignores them.
    """
    county_id = normalize_county_id(parcel_id)
    if county_id is None:
        raise HTTPException(422, f"Not a county parcel ID: {parcel_id!r}")
    analysis = source.analysis(county_id)
    if analysis is None:
        raise HTTPException(404, f"No analysis for parcel {county_id}")
    return analysis
