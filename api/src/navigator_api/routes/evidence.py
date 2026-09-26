from fastapi import APIRouter, HTTPException

from navigator_api.models import EvidenceDetail
from navigator_api.routes.deps import Source

router = APIRouter(tags=["evidence"])


@router.get("/evidence/{evidence_id}")
def evidence(evidence_id: str, source: Source) -> EvidenceDetail:
    found = source.evidence(evidence_id)
    if found is None:
        raise HTTPException(404, f"No evidence {evidence_id!r}")
    return found
