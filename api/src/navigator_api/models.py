"""Provisional API models: search, analysis, evidence and health responses.

navigator_contracts does not define SiteContext or SiteAnalysis yet, so the API serves these
models, taken from docs/proposals/ui-contracts-draft.py.txt. When the real contracts land, this
is the only module that changes: search models move to navigator_contracts/search.py (additive),
and the analysis models are replaced by imports of the real SiteAnalysis.

Known gaps against the root CLAUDE.md, to close when the contracts exist: Range is low/high
(p10/p90) with no p50, and ParcelSummary has no city block-lot.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "0.1.0"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Shared vocabulary
# ---------------------------------------------------------------------------

ProductType = Literal["adu", "duplex", "townhomes", "walkup"]
ApprovalPath = Literal["by_right", "special_exception", "variance", "rezoning", "not_allowed"]
Band = Literal["fast_track", "conditions", "high_risk", "unknown"]
Severity = Literal["deal_risk", "caution", "unknown"]
Confidence = Literal["high", "medium", "low"]
OwnerType = Literal["land_bank", "ura", "city", "private", "other_public"]
NearFeature = Literal["transit_stop", "park", "school", "grocery"]
Constraint = Literal["undermined", "flood_zone", "landslide", "combined_sewer", "steep_slope"]
SortKey = Literal["score_desc", "headroom_desc", "fastest", "cheapest"]
Outcome = Literal["granted", "denied", "withdrawn", "pending"]


class Range(Model):
    """Every estimate is a range, never a point."""

    low: float
    high: float
    unit: Literal["usd", "usd_per_sqft", "pct", "months", "sqft", "points"]


class SourceRef(Model):
    """Where a fact came from. Shown on every finding."""

    label: str = Field(description="Short display label, e.g. 'City steep slopes 25%+'")
    dataset: str = Field(description="Dataset or publisher, e.g. 'WPRDC'")
    as_of: date | None = None
    url: str | None = None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class ProductFilter(Model):
    type: ProductType
    units: int | None = Field(default=None, ge=1, le=24)


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
    approval_paths: list[ApprovalPath] = Field(default_factory=list, description="Empty = any path")
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
        default=None, ge=0, le=100, description="Max share of lot at 25%+ slope"
    )
    exclude_constraints: list[Constraint] = Field(default_factory=list)
    include_unknowns: bool = True
    max_months_to_permit: int | None = Field(default=None, ge=1, le=60)
    show_assemblies: bool = False
    show_near_misses: bool = False
    sort: SortKey = "score_desc"


class Reading(Model):
    """How one phrase of the user's text was interpreted. Shown in the AI search preview."""

    phrase: str
    interpreted_as: str


class ParseRequest(Model):
    text: str
    current_filters: SearchFilters | None = None


class ParseResult(Model):
    filters: SearchFilters
    readings: list[Reading] = Field(default_factory=list)
    not_understood: list[str] = Field(default_factory=list)
    detected: Literal["parcel_id", "address", "description"] = "description"


class ProgramOption(Model):
    product: ProductType
    units: int
    sqft_each: int | None = None
    tenure: Literal["for_sale", "rental"] = "for_sale"
    margin_pct: Range
    months_to_permit_ready: Range
    approval_path: ApprovalPath
    relief: list[str] = Field(
        default_factory=list, description="Code sections needing relief, e.g. '§ 911.02'"
    )
    code_basis: str | None = Field(
        default=None, description="e.g. 'By-right under Title Nine as of Sep 2026 · § 903.03'"
    )
    precedent_granted: int | None = None
    precedent_total: int | None = None
    evidence_id: str | None = None


class ParcelSummary(Model):
    """One row in the results list, one feature on the map, one inspector card."""

    parcel_id: str
    display_name: str
    address: str | None = None
    neighborhood: str
    zoning_district: str
    lot_area_sqft: float
    current_use: str
    owner_type: OwnerType
    assessed_value: float | None = None
    listed_price: float | None = None
    centroid: tuple[float, float] = Field(description="[lon, lat]")
    score: int | None = Field(default=None, ge=0, le=100)
    band: Band
    best_program: ProgramOption | None = None
    top_risk: str | None = None
    top_risk_severity: Severity | None = None
    max_land_price: Range | None = None
    rank: int | None = None


class SearchResponse(Model):
    total: int
    filters: SearchFilters
    results: list[ParcelSummary]


class LookupMatch(Model):
    kind: Literal["parcel_id", "address"]
    parcel: ParcelSummary
    matched_text: str


# ---------------------------------------------------------------------------
# Site analysis (the report)
# ---------------------------------------------------------------------------


class ScoreComponent(Model):
    key: str = Field(description="e.g. approval_path, site_cost, land_headroom")
    label: str
    points: int
    max_points: int
    note: str


class Verdict(Model):
    band: Band
    score: int | None = None
    score_range: Range | None = None
    headline: str = Field(
        description="One or two sentences. Screening language only, never 'approved' or "
        "'compliant'."
    )


class HeadlineNumbers(Model):
    approval_path: ApprovalPath
    approval_summary: str
    months_to_permit_ready: Range
    site_cost_premium: Range
    site_cost_summary: str
    max_land_price: Range
    target_margin_pct: float
    listed_price: float | None = None
    comps_count: int
    comps_radius_mi: float
    comps_window_months: int


class Finding(Model):
    id: str
    severity: Severity
    title: str
    detail: str
    impact_cost: Range | None = None
    impact_months: Range | None = None
    impact_label: str
    sources: list[SourceRef]
    confidence: Confidence
    confidence_note: str | None = None
    resolved_by_step: int | None = None
    evidence_id: str | None = None


class ClearedCheck(Model):
    label: str
    source: SourceRef | None = None


class NextStep(Model):
    order: int
    title: str
    why: str
    who: str
    cost: Range = Field(description="low=high=0 means free")
    duration_label: str


class Assumption(Model):
    key: str
    label: str
    value: Range | float | str
    source_label: str
    editable: bool = True


class AnalysisMeta(Model):
    contract_version: str = CONTRACT_VERSION
    rules_version: str
    data_refreshed: date
    engine_version: str
    illustrative: bool = False


class SiteAnalysis(Model):
    parcel: ParcelSummary
    verdict: Verdict
    score_breakdown: list[ScoreComponent]
    headline_numbers: HeadlineNumbers
    findings: list[Finding] = Field(description="Ordered worst first")
    cleared: list[ClearedCheck]
    best_by_right: ProgramOption | None = None
    best_with_approvals: ProgramOption | None = None
    next_steps: list[NextStep] = Field(description="Ordered cheapest deal-killers first")
    assumptions: list[Assumption]
    meta: AnalysisMeta


# ---------------------------------------------------------------------------
# Evidence drawer
# ---------------------------------------------------------------------------


class Case(Model):
    case_id: str
    neighborhood: str
    request: str
    outcome: Outcome
    months_to_decision: int | None = None
    source_url: str | None = None


class CodeReference(Model):
    section: str
    as_of: date
    summary: str
    url: str | None = None


class Evidence(Model):
    id: str
    kind: Literal["zoning_relief", "physical", "infrastructure", "market"]
    title: str
    applies_to: str
    code: CodeReference | None = None
    precedent_granted: int | None = None
    precedent_total: int | None = None
    median_months: float | None = None
    cases: list[Case] = Field(default_factory=list)
    ai_extracted: bool = False
    confidence: Confidence
    confidence_note: str
    how_to_resolve: str


# ---------------------------------------------------------------------------
# Neighborhood summary (3D score view side panel)
# ---------------------------------------------------------------------------


class Blocker(Model):
    label: str
    lots: int


class NeighborhoodSummary(Model):
    name: str
    product: ProductFilter
    counts: dict[Band, int]
    blockers: list[Blocker]
    near_misses: int
    assemblies: int


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class Versions(Model):
    """What produced the data being served. Every SiteAnalysis stamps the same versions."""

    engine: str
    ruleset: str
    schema_version: str
    data_as_of: date


class Health(Model):
    status: Literal["ok"] = "ok"
    site_source: Literal["mock", "pipeline"]
    illustrative: bool
    versions: Versions
