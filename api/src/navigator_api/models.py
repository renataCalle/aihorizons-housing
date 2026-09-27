"""API models: everything the API serves besides the contracts themselves.

SiteContext and SiteAnalysis come from navigator_contracts. The models here are API-local and
additive: parcel summaries for lists, the map and the report header; search filters; evidence
for the drawer; health. The search models are proposed for navigator_contracts/search.py once
both owners agree (docs/proposals/). This is the module to change when that happens.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from navigator_contracts import Range, SiteAnalysis
from navigator_contracts.common import Confidence, Interval
from navigator_contracts.site_analysis import (
    Band,
    Category,
    CheckResult,
    CodeSection,
    CostRange,
    OptionLabel,
    ProductType,
    Severity,
    Step,
    Versions,
)
from navigator_contracts.site_context import OwnerType


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Parcels
# ---------------------------------------------------------------------------


class LeadOption(Model):
    """The engine's headline program (`metrics.option`), for lists and the inspector card."""

    label: OptionLabel
    product_type: ProductType
    units: int
    relief: list[str] = Field(description="Empty = by right")
    margin: Range | None = Field(default=None, description="Margin on cost, as a fraction")


class ProgramFit(Model):
    """One building type the engine tested on the lot (`rule_checks.programs`)."""

    product_type: ProductType
    units: int
    outcome: Literal["by_right", "needs_approval", "rejected"]
    relief_types: list[str] = Field(description="Approvals that fix the failing rules")


class ParcelSummary(Model):
    """One row in the results list, one feature on the map, the report header.

    Facts come from SiteContext, judgments are copied from the engine's SiteAnalysis; the API
    computes nothing here.
    """

    parcel_id: str = Field(description="Canonical 16-character county ID")
    block_lot: str | None = Field(description="Dashed city block-lot, e.g. 55-A-137")
    display_name: str
    address: str | None
    municipality: str
    neighborhood: str | None
    zoning: list[str] = Field(description="Zoning district codes on the lot")
    lot_area_sqft: float
    current_use: str
    owner_type: OwnerType
    assessed_land: float | None
    centroid: tuple[float, float] = Field(description="[lon, lat], EPSG:4326")
    candidate: bool = Field(description="False = not a development candidate (outline only)")
    illustrative: bool = Field(description="True for generated mock parcels")
    assembly_id: str | None = Field(default=None, description="Lots that work together")
    score: int | None = None
    band: Band | None = Field(default=None, description="None when there is no analysis")
    top_flag: str | None = None
    top_flag_severity: Severity | None = None
    max_land_price: Range | None = None
    lead_option: LeadOption | None = None
    months_to_permit: Range | None = None
    site_cost_premium: CostRange | None = None
    programs: list[ProgramFit] = Field(
        default_factory=list, description="Every building type the engine tested"
    )
    # Facts copied from SiteContext for search filters. None = unknown, never zero.
    has_structure: bool = False
    steep_slope_share: float | None = None
    landslide_share: float | None = None
    undermined_share: float | None = None
    flood_share: float | None = Field(default=None, description="FEMA zones, excluding X500")
    combined_sewershed: bool | None = None
    transit_distance_ft: float | None = None
    tax_lien_usd: float = 0.0


class Freshness(Model):
    """Where the report's facts came from: the stored copy, or live lookups at report time."""

    parcels_as_of: date | None = Field(description="As-of date of the parcel records")
    live: list[str] = Field(description="Layers fetched live for this report")
    live_at: datetime | None = Field(description="When the latest live lookup ran")
    fell_back: list[str] = Field(
        description="Layers whose live lookup failed, so the stored copy was used"
    )


class Program(Model):
    """A building type to score, e.g. the one a search asked for."""

    product_type: ProductType
    units: int | None = Field(default=None, description="None = the largest the zoning rules allow")


class ParcelReport(Model):
    """Everything the report panel needs: the header and the engine's analysis."""

    parcel: ParcelSummary
    analysis: SiteAnalysis | None = Field(description="None when the lot is not a candidate")
    program: Program | None = Field(
        default=None,
        description="The building the analysis scores when one was requested and could be "
        "scored; None = the engine's pick",
    )
    freshness: Freshness | None = Field(
        default=None, description="None when the facts behind the analysis are not stored"
    )


# ---------------------------------------------------------------------------
# Search (proposed for navigator_contracts/search.py)
# ---------------------------------------------------------------------------


class LookupMatch(Model):
    matched_on: Literal["county_id", "block_lot", "address"]
    parcel: ParcelSummary


class LookupResponse(Model):
    """What the search box detected, and the parcels it matches (IDs and addresses only)."""

    kind: Literal["parcel_id", "address", "description", "empty"]
    format: Literal["county", "block_lot"] | None = Field(
        default=None, description="For parcel IDs: county ID or city block-lot"
    )
    matches: list[LookupMatch]


# "administrative": approvals without a zoning board hearing, such as a lot subdivision.
ApprovalPath = Literal[
    "by_right", "administrative", "special_exception", "variance", "rezoning", "not_allowed"
]
NearFeature = Literal["transit_stop", "park", "school", "grocery"]
Constraint = Literal["undermined", "flood_zone", "landslide", "combined_sewer", "steep_slope"]
SortKey = Literal["score_desc", "headroom_desc", "fastest", "cheapest"]


class ProductFilter(Model):
    type: ProductType | None = Field(default=None, description="None = any building type")
    units: int | None = Field(default=None, ge=1, le=24, description="At least this many")


class NearFilter(Model):
    feature: NearFeature
    within_ft: int = Field(default=1320, ge=100, le=5280, description="Default: a quarter mile")


class SearchFilters(Model):
    """The single filter state shared by the manual controls, the chips and AI search."""

    product: ProductFilter | None = None
    areas: list[str] = Field(
        default_factory=list, description="Pittsburgh neighborhood names, canonical spelling"
    )
    near: list[NearFilter] = Field(default_factory=list)
    approval_paths: list[ApprovalPath] = Field(default_factory=list, description="Empty = any")
    bands: list[Band] = Field(default_factory=list, description="Empty = all bands")
    min_score: int | None = Field(default=None, ge=0, le=100)
    max_land_price: float | None = Field(default=None, ge=0, description="USD, land only")
    min_margin_pct: float | None = Field(default=None, ge=0, le=100)
    max_site_cost_premium: float | None = Field(default=None, ge=0, description="USD")
    lot_min_sqft: float | None = Field(default=None, ge=0)
    lot_max_sqft: float | None = Field(default=None, ge=0)
    vacant_only: bool = False
    owner_types: list[OwnerType] = Field(default_factory=list)
    tax_delinquent_only: bool = False
    max_steep_slope_pct: float | None = Field(
        default=None, ge=0, le=100, description="Max percent of lot at 25%+ slope"
    )
    exclude_constraints: list[Constraint] = Field(default_factory=list)
    include_unknowns: bool = True
    max_months_to_permit: int | None = Field(default=None, ge=1, le=60)
    show_assemblies: bool = False
    show_near_misses: bool = False
    sort: SortKey = "score_desc"


class Neighborhood(Model):
    name: str
    candidates: int = Field(description="Development candidates with data in this neighborhood")


class Reading(Model):
    """How one phrase of the user's text was read. Shown in the AI search preview."""

    phrase: str
    interpreted_as: str


class ParseRequest(Model):
    text: str = Field(max_length=500)
    current_filters: SearchFilters | None = None


class FilterChip(Model):
    """One active filter as the UI shows it. `key` says what removing the chip resets."""

    key: str = Field(description="SearchFilters field, or near:<feature> / constraint:<name>")
    label: str


class ParseResult(Model):
    filters: SearchFilters
    chips: list[FilterChip]
    readings: list[Reading] = Field(default_factory=list)
    not_understood: list[str] = Field(default_factory=list)
    detected: Literal["parcel_id", "address", "description"] = "description"
    parser: Literal["ai", "rules"] = Field(description="rules = basic search (AI unavailable)")


class ScoredProgram(Model):
    """The building a lot is scored on in a search: the searched building type (the engine's
    result for that type, from the results bundle's per-building rows) or the engine's pick."""

    product_type: ProductType | None = Field(
        description="None = no building the engine tested fits the lot"
    )
    units: int | None
    basis: Literal["pick", "exact", "up_to"] = Field(
        description="pick = the engine's pick; exact = the searched unit count; up_to = the "
        "largest unit count the zoning rules allow for the searched type"
    )
    score: int | None = Field(description="None = not scored (ruled out, or zoning not covered)")
    band: Band | None
    outcome: Literal["by_right", "needs_approval", "rejected", "not_covered"] | None
    relief_types: list[str] = Field(description="Approvals needed; empty = by right")
    months_to_permit: Range | None
    max_land_price: Range | None


class SearchResult(Model):
    rank: int
    parcel: ParcelSummary
    fit: ProgramFit | None = Field(description="The program that matched the product filter")
    scored: ScoredProgram | None = Field(
        default=None, description="What the lot is ranked on: the searched type, or the pick"
    )
    better_fit: ScoredProgram | None = Field(
        default=None,
        description="The engine's pick, when a building type was searched and the pick is "
        "another type",
    )


class NearMiss(Model):
    """A candidate that fails exactly one active filter."""

    parcel: ParcelSummary
    failed: FilterChip


class Assembly(Model):
    assembly_id: str
    parcel_ids: list[str]


class Suggestion(Model):
    """When nothing matches: the filter whose removal brings back the most sites."""

    remove: FilterChip
    would_return: int


class SearchResponse(Model):
    total: int
    filters: SearchFilters
    ranked_for: ProductFilter | None = Field(
        default=None, description="The building type lots are ranked for; None = best fit"
    )
    chips: list[FilterChip]
    results: list[SearchResult]
    near_misses: list[NearMiss] = Field(default_factory=list)
    assemblies: list[Assembly] = Field(default_factory=list)
    not_applied: list[FilterChip] = Field(
        default_factory=list, description="Filters the data can't answer yet; ignored"
    )
    suggestion: Suggestion | None = None


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------


class ParcelProperties(Model):
    parcel_id: str
    display_name: str
    candidate: bool
    band: Band | None
    score: int | None
    rank: int | None = None
    assembly_id: str | None = None


class ParcelFeature(Model):
    type: Literal["Feature"] = "Feature"
    geometry: dict = Field(description="GeoJSON geometry, EPSG:4326")
    properties: ParcelProperties


class ParcelFeatureCollection(Model):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ParcelFeature]


class MapFeatureProperties(Model):
    kind: Literal["transit_stop", "park", "school", "neighborhood"]
    name: str | None = None


class MapFeature(Model):
    type: Literal["Feature"] = "Feature"
    geometry: dict = Field(description="GeoJSON geometry, EPSG:4326")
    properties: MapFeatureProperties


class MapFeatureCollection(Model):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[MapFeature]


# ---------------------------------------------------------------------------
# Evidence drawer: one finding or the approvals option, formatted from SiteAnalysis and
# SiteContext (navigator_api/evidence.py)
# ---------------------------------------------------------------------------

Outcome = Literal["granted", "denied", "withdrawn", "pending", "unknown"]


class Case(Model):
    case_id: str
    area: str | None = Field(default=None, description="Neighborhood or zoning district")
    request: str | None = None
    outcome: Outcome
    months_to_decision: float | None = None
    source_url: str | None = None


class Precedent(Model):
    """Zoning board decisions near the lot. Real lots have none until decisions are
    available; generated lots carry the mockups' cases, marked illustrative."""

    status: Literal["available", "unavailable", "illustrative"]
    note: str | None = Field(default=None, description="Why decisions are unavailable")
    rule: str | None = Field(default=None, description="What the engine counts as similar")
    granted: int | None = None
    total: int | None = None
    median_months: float | None = None
    cases: list[Case] = Field(default_factory=list)
    ai_extracted: bool = False


class EvidenceSource(Model):
    source: str
    as_of: date | None
    as_of_from_provenance: bool = Field(
        default=False, description="The flag had no date; this is the layer's as-of date"
    )
    layer: str | None
    code_section: str | None
    url: str | None


class EvidenceDetail(Model):
    """What the engine and the stored facts say about one finding (`flag.<id>`) or the
    approvals option (`option.with_relief`) of one lot's report."""

    id: str = Field(description="flag.<flag id> or option.with_relief")
    kind: Literal["finding", "approvals"]
    parcel_id: str
    title: str | None = Field(description="The flag's title; None for the approvals option")
    product_type: ProductType | None = Field(default=None, description="Approvals option only")
    units: int | None = None
    category: Category
    severity: Severity | None = Field(default=None, description="Findings only")
    confidence: Confidence | None = Field(default=None, description="Findings only")
    cost_usd: Interval | None = None
    months: Interval | None = None
    months_to_permit: Range | None = Field(default=None, description="Approvals option only")
    approval_prob: Range | None = None
    approval_months: Range | None = None
    relief: list[str] = Field(default_factory=list)
    entitlement_basis: list[str] = Field(default_factory=list)
    odds_note: str | None = None
    rule_checks: list[CheckResult] = Field(
        default_factory=list, description="The rules the building fails (approvals option)"
    )
    sources: list[EvidenceSource] = Field(default_factory=list)
    code_sections: list[CodeSection] = Field(
        default_factory=list, description="The code sections this evidence cites, explained"
    )
    how_to_resolve: str | None
    resolved_by: Step | None = Field(description="The next step that resolves the finding")
    precedent: Precedent | None = Field(
        default=None, description="Zoning board decisions (approvals option only)"
    )
    illustrative: bool
    versions: Versions


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class Examples(Model):
    """Example searches for the landing page, taken from the data being served."""

    parcel_id: str = Field(description="A partial county ID, dashed")
    address: str
    prompt: str


class Health(Model):
    status: Literal["ok"] = "ok"
    site_source: Literal["mock", "pipeline"]
    illustrative: bool = Field(description="True when any served parcel is mock data")
    parcels: int
    versions: Versions
