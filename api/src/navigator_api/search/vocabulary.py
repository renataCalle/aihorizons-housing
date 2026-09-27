"""Search vocabulary: neighborhoods, aliases, product names, and the label of every filter chip.

One place for all of it, shared by the fallback parser, the AI parser's tool schema, and the
search response (docs/05-ai-search.md, "Vocabulary").
"""

from navigator_api.models import SearchFilters

# The City of Pittsburgh's 90 neighborhoods, spelled as in the city's data.
NEIGHBORHOODS = [
    "Allegheny Center", "Allegheny West", "Allentown", "Arlington", "Arlington Heights",
    "Banksville", "Bedford Dwellings", "Beechview", "Beltzhoover", "Bloomfield", "Bluff",
    "Bon Air", "Brighton Heights", "Brookline", "California-Kirkbride", "Carrick",
    "Central Business District", "Central Lawrenceville", "Central Northside",
    "Central Oakland", "Chartiers", "Chateau", "Crafton Heights", "Crawford-Roberts",
    "Duquesne Heights", "East Allegheny", "East Carnegie", "East Hills", "East Liberty",
    "Elliott", "Esplen", "Fairywood", "Fineview", "Friendship", "Garfield", "Glen Hazel",
    "Greenfield", "Hays", "Hazelwood", "Highland Park", "Homewood North", "Homewood South",
    "Homewood West", "Knoxville", "Larimer", "Lincoln Place", "Lincoln-Lemington-Belmar",
    "Lower Lawrenceville", "Manchester", "Marshall-Shadeland", "Middle Hill", "Morningside",
    "Mount Oliver", "Mount Washington", "New Homestead", "North Oakland", "North Shore",
    "Northview Heights", "Oakwood", "Overbrook", "Perry North", "Perry South", "Point Breeze",
    "Point Breeze North", "Polish Hill", "Regent Square", "Ridgemont", "Shadyside",
    "Sheraden", "South Oakland", "South Shore", "South Side Flats", "South Side Slopes",
    "Spring Garden", "Spring Hill-City View", "Squirrel Hill North", "Squirrel Hill South",
    "St. Clair", "Stanton Heights", "Strip District", "Summer Hill", "Swisshelm Park",
    "Terrace Village", "Troy Hill", "Upper Hill", "Upper Lawrenceville", "West End",
    "West Oakland", "Westwood", "Windgap",
]  # fmt: skip

# Names people use that the city splits into several neighborhoods (docs/05).
ALIASES = {
    "lawrenceville": ["Lower Lawrenceville", "Central Lawrenceville", "Upper Lawrenceville"],
    "homewood": ["Homewood North", "Homewood South", "Homewood West"],
    "the hill": [
        "Crawford-Roberts", "Middle Hill", "Upper Hill", "Terrace Village", "Bedford Dwellings",
    ],
    "hill district": [
        "Crawford-Roberts", "Middle Hill", "Upper Hill", "Terrace Village", "Bedford Dwellings",
    ],
    "squirrel hill": ["Squirrel Hill North", "Squirrel Hill South"],
    "oakland": ["North Oakland", "Central Oakland", "South Oakland", "West Oakland"],
    "south side": ["South Side Flats", "South Side Slopes"],
    "downtown": ["Central Business District"],
    "the strip": ["Strip District"],
    "mt washington": ["Mount Washington"],
    "mt. washington": ["Mount Washington"],
    "mt oliver": ["Mount Oliver"],
    "mt. oliver": ["Mount Oliver"],
}  # fmt: skip

PRODUCT_LABEL = {
    "single_family": "Single family",
    "duplex": "Duplex",
    "triplex": "Triplex",
    "townhome": "Townhomes",
    "walkup": "Walk-up",
}

APPROVAL_LABEL = {
    "by_right": "By right",
    "administrative": "Administrative approval",
    "special_exception": "Special exception",
    "variance": "Variance",
    "rezoning": "Rezoning",
    "not_allowed": "Not allowed",
}

# "Allow variances" = everything short of a rezoning.
VARIANCES_OK = ["by_right", "administrative", "special_exception", "variance"]
PUBLIC_OWNERS = ["land_bank", "ura", "city"]

OWNER_LABEL = {
    "private": "Private",
    "land_bank": "Land bank",
    "ura": "URA",
    "city": "City",
    "other_public": "Other public",
}
NEAR_LABEL = {
    "transit_stop": "transit",
    "park": "a park",
    "school": "a school",
    "grocery": "a grocery store",
}
CONSTRAINT_LABEL = {
    "undermined": "No undermining",
    "flood_zone": "Outside flood zones",
    "landslide": "No landslide-prone ground",
    "combined_sewer": "Outside combined sewersheds",
    "steep_slope": "No steep slope",
}
BAND_LABEL = {
    "fast_track": "Fast track",
    "feasible_with_conditions": "Conditions",
    "high_risk": "High risk",
    "not_scored": "Not scored",
}
SORT_LABEL = {
    "score_desc": "Best score",
    "headroom_desc": "Most land headroom",
    "fastest": "Fastest",
    "cheapest": "Cheapest land",
}

QUARTER_MILE_FT = 1320
FLAT_MAX_STEEP_PCT = 5


def money(value: float) -> str:
    """$25k, $1.2M"""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M".replace(".0M", "M")
    if value >= 1_000:
        return f"${value / 1_000:.0f}k"
    return f"${value:.0f}"


def distance(feet: int) -> str:
    return "¼ mi" if feet == QUARTER_MILE_FT else f"{feet:,} ft"


def chip_labels(f: SearchFilters) -> list[tuple[str, str]]:
    """(key, label) for every active filter, in display order. Removing a chip resets `key`."""
    chips: list[tuple[str, str]] = []
    if f.product:
        name = PRODUCT_LABEL[f.product.type] if f.product.type else None
        units = f.product.units
        if name and units:
            label = f"{name} · {units}"
        elif name:
            label = name
        else:
            label = f"{units}+ units" if units else "Any building"
        chips.append(("product", label))
    chips += [(f"area:{area}", area) for area in f.areas]
    if f.approval_paths:
        paths = sorted(f.approval_paths, key=list(APPROVAL_LABEL).index)
        if paths == ["by_right"]:
            label = "By-right only"
        elif paths == VARIANCES_OK:
            label = "Variances OK"
        else:
            label = ", ".join(APPROVAL_LABEL[p] for p in paths)
        chips.append(("approval_paths", label))
    if f.max_land_price is not None:
        chips.append(("max_land_price", f"Land ≤ {money(f.max_land_price)}"))
    chips += [
        (f"near:{n.feature}", f"Within {distance(n.within_ft)} of {NEAR_LABEL[n.feature]}")
        for n in f.near
    ]
    if f.max_steep_slope_pct is not None:
        pct = f.max_steep_slope_pct
        label = (
            "No steep slope"
            if pct == 0
            else f"Flat lots (under {pct:g}% steep slope)"
            if pct <= FLAT_MAX_STEEP_PCT
            else f"Steep slope ≤ {pct:g}%"
        )
        chips.append(("max_steep_slope_pct", label))
    chips += [(f"constraint:{c}", CONSTRAINT_LABEL[c]) for c in f.exclude_constraints]
    if f.bands:
        chips.append(("bands", " or ".join(BAND_LABEL[b] for b in f.bands)))
    if f.min_score is not None:
        chips.append(("min_score", f"Score ≥ {f.min_score}"))
    if f.min_margin_pct is not None:
        chips.append(("min_margin_pct", f"Margin ≥ {f.min_margin_pct:g}%"))
    if f.max_site_cost_premium is not None:
        chips.append(("max_site_cost_premium", f"Site costs ≤ {money(f.max_site_cost_premium)}"))
    if f.max_months_to_permit is not None:
        chips.append(("max_months_to_permit", f"Permit-ready ≤ {f.max_months_to_permit} months"))
    if f.lot_min_sqft is not None or f.lot_max_sqft is not None:
        lo, hi = f.lot_min_sqft, f.lot_max_sqft
        label = (
            f"Lot {lo:,.0f}–{hi:,.0f} sq ft"
            if lo is not None and hi is not None
            else f"Lot ≥ {lo:,.0f} sq ft"
            if lo is not None
            else f"Lot ≤ {hi:,.0f} sq ft"
        )
        chips.append(("lot_size", label))
    if f.vacant_only:
        chips.append(("vacant_only", "Vacant only"))
    if f.owner_types:
        label = (
            "Public land"
            if sorted(f.owner_types) == sorted(PUBLIC_OWNERS)
            else ", ".join(OWNER_LABEL[o] for o in f.owner_types)
        )
        chips.append(("owner_types", label))
    if f.tax_delinquent_only:
        chips.append(("tax_delinquent_only", "Tax-delinquent"))
    if not f.include_unknowns:
        chips.append(("include_unknowns", "Hide unknowns"))
    if f.show_assemblies:
        chips.append(("show_assemblies", "Show assemblies"))
    if f.show_near_misses:
        chips.append(("show_near_misses", "Show near misses"))
    return chips


def without(f: SearchFilters, key: str) -> SearchFilters:
    """The filters with one chip removed."""
    defaults = SearchFilters()
    if key.startswith("area:"):
        return f.model_copy(update={"areas": [a for a in f.areas if a != key[5:]]})
    if key.startswith("near:"):
        return f.model_copy(update={"near": [n for n in f.near if n.feature != key[5:]]})
    if key.startswith("constraint:"):
        rest = [c for c in f.exclude_constraints if c != key[11:]]
        return f.model_copy(update={"exclude_constraints": rest})
    if key == "lot_size":
        return f.model_copy(update={"lot_min_sqft": None, "lot_max_sqft": None})
    return f.model_copy(update={key: getattr(defaults, key)})
