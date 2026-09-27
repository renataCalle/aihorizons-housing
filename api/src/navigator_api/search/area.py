"""The searched lots at a glance: the 3D view's panel.

Counting only. Bands are the ones the search ranks on; "what holds sites back" adds up each
lot's `score_breakdown` (the engine's counterfactual points lost per driver) by driver. Each
breakdown belongs to the lot's stored analysis, the engine's best fit for that lot.
"""

from collections import defaultdict
from collections.abc import Callable

from navigator_api.models import AreaSummary, Blocker, SearchFilters, SearchResponse
from navigator_contracts import SiteAnalysis

DRIVER_LABEL = {
    "steep_slope": "Steep slope",
    "landslide_prone": "Landslide-prone",
    "undermined": "Undermined",
    "flood_zone": "Flood zone",
    "combined_sewer": "Combined sewer area",
    "env_nearby": "Environmental records nearby",
    "tax_liens": "Tax liens",
    "frontage": "Street frontage not verified",
    "condemned": "Condemned structure",
    "demolition": "Demolition needed",
    "split_zoned": "Split zoning",
    "contextual_setbacks": "Relies on contextual setbacks",
    "relief": "Approvals needed",
}

MAX_BLOCKERS = 5


def driver_of(flag_id: str) -> str:
    """ "relief:variance+subdivision" -> "relief"; flag ids stay as they are."""
    return flag_id.split(":")[0]


def summarize_area(
    response: SearchResponse,
    near_misses: int,
    analysis: Callable[[str], SiteAnalysis | None],
) -> AreaSummary:
    bands: dict[str, int] = defaultdict(int)
    lost: dict[str, list[float]] = defaultdict(list)
    for r in response.results:
        band = r.scored.band if r.scored and r.scored.band else r.parcel.band or "not_scored"
        bands[band] += 1
        a = analysis(r.parcel.parcel_id)
        per_driver: dict[str, float] = defaultdict(float)
        for item in a.score_breakdown if a else []:
            per_driver[driver_of(item.driver_flag_id)] += item.points_lost
        for driver, points in per_driver.items():
            if points > 0:
                lost[driver].append(points)
    blockers = sorted(
        (
            Blocker(
                driver=d,
                label=DRIVER_LABEL.get(d, d.replace("_", " ").capitalize()),
                lots=len(points),
                avg_points=round(sum(points) / len(points), 1),
            )
            for d, points in lost.items()
        ),
        key=lambda b: (-b.lots * b.avg_points, b.label),
    )
    return AreaSummary(
        lots=response.total,
        ranked_for=response.ranked_for,
        bands=dict(bands),
        blockers=blockers[:MAX_BLOCKERS],
        near_misses=near_misses,
        assemblies=len(response.assemblies),
    )


def with_extras(f: SearchFilters) -> SearchFilters:
    """The same search, also counting near misses and assemblies."""
    return f.model_copy(update={"show_near_misses": True, "show_assemblies": True})
