from fastapi import APIRouter, HTTPException

from navigator_api.models import ParcelReport
from navigator_api.parcel_ids import normalize_county_id
from navigator_api.routes.deps import Source

router = APIRouter(tags=["parcels"])


@router.get("/parcels/{parcel_id}")
def parcel_report(parcel_id: str, source: Source) -> ParcelReport:
    """Report header and the engine's analysis, by county parcel ID (compact or dashed)."""
    county_id = normalize_county_id(parcel_id)
    if county_id is None:
        raise HTTPException(422, f"Not a county parcel ID: {parcel_id!r}")
    summary = source.summary(county_id)
    if summary is None:
        raise HTTPException(404, f"No parcel {county_id}")
    return ParcelReport(parcel=summary, analysis=source.analysis(county_id))
