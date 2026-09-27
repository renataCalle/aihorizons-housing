from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from navigator_api.evidence import build_evidence
from navigator_api.models import EvidenceDetail
from navigator_api.routes.deps import Source
from navigator_api.routes.parcels import scored_report
from navigator_contracts.site_analysis import ProductType

router = APIRouter(tags=["evidence"])


@router.get("/parcels/{parcel_id}/evidence/{evidence_id}")
def evidence(
    parcel_id: str,
    evidence_id: str,
    source: Source,
    product_type: ProductType | None = None,
    units: Annotated[int | None, Query(ge=1, le=50)] = None,
) -> EvidenceDetail:
    """One finding (`flag.<flag id>`) or the approvals option (`option.with_relief`) of the
    lot's report, for the same building type as the report (`product_type`, `units`)."""
    r = scored_report(parcel_id, source, product_type, units)
    if r.analysis is None:
        raise HTTPException(404, f"No analysis for {r.summary.parcel_id}")
    found = build_evidence(
        evidence_id,
        r.summary.parcel_id,
        r.analysis,
        r.context,
        illustrative=r.summary.illustrative,
        mock_precedent=source.mock_precedent(),
    )
    if found is None:
        raise HTTPException(404, f"No evidence {evidence_id!r} for {r.summary.parcel_id}")
    return found
