from fastapi import APIRouter, HTTPException

from navigator_api.models import Freshness, ParcelReport
from navigator_api.parcel_ids import normalize_county_id
from navigator_api.routes.deps import Source
from navigator_contracts import SiteContext

router = APIRouter(tags=["parcels"])


def freshness(context: SiteContext) -> Freshness:
    """Which facts were looked up live for this report, from the context's provenance."""
    prov = context.provenance
    live = [k for k, s in prov.items() if s.retrieved == "live"]
    parcels = prov.get("parcels")
    return Freshness(
        parcels_as_of=parcels.as_of if parcels else None,
        live=live,
        live_at=max((t for k in live if (t := prov[k].retrieved_at)), default=None),
        fell_back=[k for k, s in prov.items() if (s.note or "").startswith("Live lookup failed")],
    )


@router.get("/parcels/{parcel_id}")
def parcel_report(parcel_id: str, source: Source) -> ParcelReport:
    """Report header, the engine's analysis, and where its facts came from, by county ID."""
    county_id = normalize_county_id(parcel_id)
    if county_id is None:
        raise HTTPException(422, f"Not a county parcel ID: {parcel_id!r}")
    summary = source.summary(county_id)
    if summary is None:
        raise HTTPException(404, f"No parcel {county_id}")
    context = source.context(county_id)
    return ParcelReport(
        parcel=summary,
        analysis=source.analysis(county_id),
        freshness=freshness(context) if context else None,
    )
