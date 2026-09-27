"""Which nearby zoning board cases count as precedent for an option's approvals (a judgment).

A case is similar when it asked for the same kind of zoning board approval, in the same base
district, nearby, and recently. The API turns the similar cases into the evidence table
(granted count, median months); it does not choose them.
"""

from datetime import date

ZBA_RELIEF = {"variance", "special_exception", "use_variance"}  # decided by the Zoning Board
SIMILAR_RADIUS_FT = 2_640  # half a mile
SIMILAR_YEARS = 5
RULE = (
    "Same zoning board approval type (variance or special exception), same base district "
    f"(e.g. R1D for R1D-M), within {SIMILAR_RADIUS_FT / 5280:.1f} mi, decided in the "
    f"{SIMILAR_YEARS} years before the newest case in the data"
)


def _norm(kind: str) -> str:
    return kind.strip().lower().replace(" ", "_").replace("-", "_")


def _base(district: str | None) -> str | None:
    return district.split("-")[0].upper() if district else None


def _day(value) -> date | None:
    return date.fromisoformat(str(value)[:10]) if value else None


def similar_cases(ctx: dict, relief_types: list[str], district: str | None) -> list[str] | None:
    """case_ids of nearby cases comparable to these approvals.

    None when the option needs no zoning board approval, or when cases are unavailable
    (zba_cases_nearby is None); [] when there are cases but none is similar.
    """
    needs = {_norm(t) for t in relief_types} & ZBA_RELIEF
    cases = ctx.get("zba_cases_nearby")
    if not needs or cases is None:
        return None
    # "Recent" is measured from the newest decision in the data, so the answer does not
    # depend on the day the engine runs.
    dated = [d for d in (_day(c.get("decision_date")) for c in cases) if d]
    newest = max(dated) if dated else None
    out = []
    for c in cases:
        if not needs & {_norm(t) for t in c.get("relief_types") or []}:
            continue
        if c.get("district") and district and _base(c["district"]) != _base(district):
            continue
        if c.get("distance_ft") is not None and c["distance_ft"] > SIMILAR_RADIUS_FT:
            continue
        decided = _day(c.get("decision_date"))
        if newest and decided and (newest - decided).days > SIMILAR_YEARS * 365.25:
            continue
        out.append(c["case_id"])
    return out
