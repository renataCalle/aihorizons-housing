"""Filter, sort and rank parcel summaries (docs/05: the query engine is deterministic).

Everything judged here was judged by the engine: which programs fit a lot, its score and band,
its costs and months. This module only compares those to the user's filters.

Score, band, months and max land price come from what the lot is scored on (search/programs.py):
the searched building type when the filters name one, else the engine's pick.
"""

import math
from collections.abc import Callable

from navigator_api.models import (
    Assembly,
    FilterChip,
    MapFeatureCollection,
    NearMiss,
    ParcelSummary,
    ProgramFit,
    ScoredProgram,
    SearchFilters,
    SearchResponse,
    SearchResult,
    Suggestion,
)
from navigator_api.search.programs import better_fit, scored_for
from navigator_api.search.vocabulary import chip_labels

# Relief types the engine names, grouped into the approval paths users filter on.
VARIANCE_RELIEF = {"variance", "use_variance"}
EXCEPTION_RELIEF = {"special_exception"}
ADMINISTRATIVE_RELIEF = {"subdivision", "administrator_exception"}

Check = Callable[[ParcelSummary], bool]


def approval_path(outcome: str, relief_types: list[str]) -> str:
    if outcome == "by_right":
        return "by_right"
    if outcome == "rejected":
        return "not_allowed"
    reliefs = set(relief_types)
    if reliefs & VARIANCE_RELIEF:
        return "variance"
    if reliefs & EXCEPTION_RELIEF:
        return "special_exception"
    if reliefs <= ADMINISTRATIVE_RELIEF:
        return "administrative"
    return "variance"


def _relief_type(relief: str) -> str:
    """ "variance (903.03)" -> "variance" """
    return relief.split(" (")[0].strip().lower().replace(" ", "_")


def matching_programs(s: ParcelSummary, f: SearchFilters) -> list[ProgramFit]:
    """Programs the engine found possible that satisfy the product and approval filters."""
    fits = [p for p in s.programs if p.outcome != "rejected"]
    if f.product:
        if f.product.type:
            fits = [p for p in fits if p.product_type == f.product.type]
        if f.product.units:
            fits = [p for p in fits if p.units >= f.product.units]
    if f.approval_paths:
        fits = [p for p in fits if approval_path(p.outcome, p.relief_types) in f.approval_paths]
    # Fewest approvals first, then the smallest program that meets the request.
    return sorted(fits, key=lambda p: (p.outcome != "by_right", len(p.relief_types), p.units))


def _haversine_ft(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 20_902_231 * math.asin(math.sqrt(h))  # Earth radius in feet


def _points(features: MapFeatureCollection, kind: str) -> list[tuple[float, float]]:
    """Points for a feature kind; polygons are reduced to the average of their outer ring."""
    out = []
    for feat in features.features:
        if feat.properties.kind != kind:
            continue
        geom = feat.geometry
        if geom["type"] == "Point":
            out.append(tuple(geom["coordinates"][:2]))
        elif geom["type"] == "Polygon":
            ring = geom["coordinates"][0][:-1]
            out.append((sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)))
    return out


def _known(value, test: Callable[[object], bool], unknown_ok: bool) -> bool:
    """A missing fact passes only when the user includes unknowns. Unknown is never clear."""
    return unknown_ok if value is None else test(value)


def build_checks(
    f: SearchFilters,
    features: MapFeatureCollection,
    scored: dict[str, ScoredProgram] | None = None,
) -> tuple[dict[str, Check], list[str]]:
    """One named check per active chip, plus the chips the data can't answer yet. Score, band
    and months are read from `scored` (what each lot is ranked on) when given."""
    unk = f.include_unknowns
    scored = scored or {}

    def band(s: ParcelSummary):
        return scored[s.parcel_id].band if s.parcel_id in scored else s.band

    def score(s: ParcelSummary):
        return scored[s.parcel_id].score if s.parcel_id in scored else s.score

    def months(s: ParcelSummary):
        return scored[s.parcel_id].months_to_permit if s.parcel_id in scored else s.months_to_permit

    checks: dict[str, Check] = {}
    not_applied: list[str] = []

    if f.product or f.approval_paths:
        key = "product" if f.product else "approval_paths"
        if f.product:
            # The product alone ("3 townhomes fit"), then with the approval path ("by right").
            any_path = f.model_copy(update={"approval_paths": []})
            checks["product"] = lambda s: bool(matching_programs(s, any_path))
            if f.approval_paths:
                checks["approval_paths"] = lambda s: bool(matching_programs(s, f))
        else:

            def lead_path(s: ParcelSummary) -> bool:
                if not s.lead_option:
                    return False
                outcome = "needs_approval" if s.lead_option.relief else "by_right"
                reliefs = [_relief_type(r) for r in s.lead_option.relief]
                return approval_path(outcome, reliefs) in f.approval_paths

            checks[key] = lead_path

    if f.areas:
        # Areas are alternatives: a lot is in one neighborhood, so it matches if it's in any.
        # One area keeps its own chip key; several are one check, removed together.
        area_key = f"area:{f.areas[0]}" if len(f.areas) == 1 else "areas"
        checks[area_key] = lambda s: s.neighborhood in f.areas
    if f.max_land_price is not None:
        # Land price = assessed land value until listing prices exist.
        checks["max_land_price"] = lambda s: _known(
            s.assessed_land, lambda v: v <= f.max_land_price, unk
        )
    for near in f.near:
        key = f"near:{near.feature}"
        if near.feature == "transit_stop":
            checks[key] = lambda s, ft=near.within_ft: _known(
                s.transit_distance_ft, lambda v: v <= ft, unk
            )
            continue
        points = _points(features, near.feature)
        if not points:
            not_applied.append(key)
            continue
        checks[key] = lambda s, pts=points, ft=near.within_ft: any(
            _haversine_ft(s.centroid, p) <= ft for p in pts
        )
    if f.max_steep_slope_pct is not None:
        checks["max_steep_slope_pct"] = lambda s: _known(
            s.steep_slope_share, lambda v: v * 100 <= f.max_steep_slope_pct, unk
        )
    facts = {
        "undermined": lambda s: s.undermined_share,
        "flood_zone": lambda s: s.flood_share,
        "landslide": lambda s: s.landslide_share,
        "steep_slope": lambda s: s.steep_slope_share,
        "combined_sewer": lambda s: s.combined_sewershed,
    }
    for c in f.exclude_constraints:
        checks[f"constraint:{c}"] = lambda s, get=facts[c]: _known(get(s), lambda v: not v, unk)
    if f.bands:
        checks["bands"] = lambda s: band(s) in f.bands
    if f.min_score is not None:
        checks["min_score"] = lambda s: (v := score(s)) is not None and v >= f.min_score
    if f.min_margin_pct is not None:
        checks["min_margin_pct"] = lambda s: (
            bool(s.lead_option and s.lead_option.margin)
            and s.lead_option.margin.p50 * 100 >= f.min_margin_pct
        )
    if f.max_site_cost_premium is not None:
        checks["max_site_cost_premium"] = lambda s: _known(
            s.site_cost_premium, lambda v: v.high <= f.max_site_cost_premium, unk
        )
    if f.max_months_to_permit is not None:
        checks["max_months_to_permit"] = lambda s: _known(
            months(s), lambda v: v.p50 <= f.max_months_to_permit, unk
        )
    if f.lot_min_sqft is not None or f.lot_max_sqft is not None:
        lo, hi = f.lot_min_sqft or 0, f.lot_max_sqft or math.inf
        checks["lot_size"] = lambda s: lo <= s.lot_area_sqft <= hi
    if f.vacant_only:
        checks["vacant_only"] = lambda s: not s.has_structure
    if f.owner_types:
        checks["owner_types"] = lambda s: s.owner_type in f.owner_types
    if f.tax_delinquent_only:
        checks["tax_delinquent_only"] = lambda s: s.tax_lien_usd > 0
    if not f.include_unknowns:
        checks["include_unknowns"] = lambda s: band(s) not in (None, "not_scored")
    return checks, not_applied


def _sort_key(
    f: SearchFilters, scored: dict[str, ScoredProgram]
) -> Callable[[ParcelSummary], tuple]:
    def score(s: ParcelSummary) -> float:
        value = scored[s.parcel_id].score
        return -(value if value is not None else -1)

    def land(s: ParcelSummary) -> float:
        value = scored[s.parcel_id].max_land_price
        return -(value.p50 - (s.assessed_land or 0)) if value else math.inf

    def months(s: ParcelSummary) -> float:
        value = scored[s.parcel_id].months_to_permit
        return value.p50 if value else math.inf

    if f.sort == "headroom_desc":
        return lambda s: (land(s), score(s))
    if f.sort == "fastest":
        return lambda s: (months(s), score(s))
    if f.sort == "cheapest":
        return lambda s: (s.assessed_land if s.assessed_land is not None else math.inf, score(s))
    return lambda s: (score(s), s.display_name)


def search(
    summaries: list[ParcelSummary],
    f: SearchFilters,
    features: MapFeatureCollection,
    program_rows: Callable[[str], dict[str, ScoredProgram]] = lambda _: {},
) -> SearchResponse:
    """`program_rows` gives the engine's result per building type for a lot; with a building
    type in the filters, lots are ranked on that type's row instead of the engine's pick."""
    candidates = [s for s in summaries if s.candidate]
    by_type = f.product if f.product and f.product.type else None
    scored = {s.parcel_id: scored_for(s, program_rows(s.parcel_id), by_type) for s in candidates}
    checks, not_applied_keys = build_checks(f, features, scored)
    labels = dict(chip_labels(f))
    labels["areas"] = "Areas: " + ", ".join(f.areas)

    def failures(s: ParcelSummary) -> list[str]:
        return [key for key, check in checks.items() if not check(s)]

    failed = {s.parcel_id: failures(s) for s in candidates}
    key = _sort_key(f, scored)
    matches = sorted((s for s in candidates if not failed[s.parcel_id]), key=key)

    results = [
        SearchResult(
            rank=i + 1,
            parcel=s,
            fit=next(iter(matching_programs(s, f)), None) if f.product else None,
            scored=scored[s.parcel_id],
            better_fit=better_fit(s, scored[s.parcel_id]) if by_type else None,
        )
        for i, s in enumerate(matches)
    ]

    near_misses = []
    if f.show_near_misses:
        near_misses = [
            NearMiss(parcel=s, failed=FilterChip(key=keys[0], label=labels.get(keys[0], keys[0])))
            for s in sorted(candidates, key=key)
            if len(keys := failed[s.parcel_id]) == 1
        ]

    assemblies: list[Assembly] = []
    if f.show_assemblies:
        groups: dict[str, list[str]] = {}
        for s in candidates:
            in_area = not f.areas or s.neighborhood in f.areas
            if s.assembly_id and in_area:
                groups.setdefault(s.assembly_id, []).append(s.parcel_id)
        assemblies = [Assembly(assembly_id=k, parcel_ids=v) for k, v in sorted(groups.items())]

    suggestion = None
    if not results and checks:
        # Which single chip, removed, brings back the most sites?
        counts = {key: sum(1 for s in candidates if failed[s.parcel_id] == [key]) for key in checks}
        best = max(counts, key=lambda k: counts[k])
        if counts[best]:
            suggestion = Suggestion(
                remove=FilterChip(key=best, label=labels.get(best, best)),
                would_return=counts[best],
            )

    return SearchResponse(
        total=len(results),
        filters=f,
        ranked_for=by_type,
        chips=[FilterChip(key=k, label=v) for k, v in chip_labels(f)],
        results=results,
        near_misses=near_misses,
        assemblies=assemblies,
        not_applied=[FilterChip(key=k, label=labels.get(k, k)) for k in not_applied_keys],
        suggestion=suggestion,
    )
