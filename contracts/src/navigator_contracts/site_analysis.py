"""SiteAnalysis: judgments about one site, produced by the engine, rendered by the UI.

The UI renders flags, options, next steps and assumptions generically from these arrays, so
a new flag type or assumption needs no frontend change. Screening language only.
"""

from datetime import date
from typing import Literal

from pydantic import Field

from navigator_contracts.common import Confidence, Contract, Interval, Range

Band = Literal["fast_track", "feasible_with_conditions", "high_risk", "not_scored"]
Category = Literal["zoning", "physical", "environmental", "infrastructure", "market"]
Severity = Literal["high", "medium", "low", "unknown"]
OptionLabel = Literal["by_right", "with_relief"]
ProductType = Literal["single_family", "duplex", "triplex", "townhome", "walkup"]
ComponentKey = Literal["approval_path", "site_cost", "land_headroom"]


class ScoreComponent(Contract):
    """One bar of "Where the score comes from". Points of all components sum to the score."""

    key: ComponentKey
    label: str
    points: int
    max_points: int  # approval_path 35, site_cost 35, land_headroom 30
    note: str  # one line: why the component scored what it did


class Verdict(Contract):
    score: int | None = Field(ge=0, le=100)  # None when not scored (zoning not covered)
    score_range: Range | None
    band: Band  # >= 75 fast track, 50-74 with conditions, < 50 high risk
    headline: str
    land_risk: str | None  # e.g. "High risk at the asking price"
    components: list[ScoreComponent]


class Narrative(Contract):
    summary: str | None  # one sentence for the verdict card; numbers only from fields


class LandBasis(Contract):
    value: float
    source: str  # "user input" (asking price) or the assessed-value note


class CostRange(Contract):
    low: float
    high: float
    drivers: list[str]  # flag titles, largest cost first


class Gap(Contract):
    low: float
    high: float


class Comps(Contract):
    count: int
    radius_mi: float
    window_months: int


class Metrics(Contract):
    """Headline numbers for the leading option (`option`)."""

    option: OptionLabel
    months_to_permit: Range
    approval_prob: Range
    max_land_price: Range  # at the target margin; negative = costs exceed value
    land_basis: LandBasis
    site_cost_premium: CostRange
    land_over_max: Gap | None  # land price above max land price; None if it isn't
    comps: Comps


class Evidence(Contract):
    source: str
    as_of: date | None
    layer: str | None
    code_section: str | None
    url: str | None


class Flag(Contract):
    id: str
    category: Category
    severity: Severity  # UI: high = deal risk, medium = caution, unknown = never clean
    title: str
    cost_usd: Interval | None
    months: Interval | None
    evidence: list[Evidence]
    confidence: Confidence
    resolution: str  # how to resolve it
    resolved_by_step: int | None  # next_steps[].order that resolves it


class ProgramOption(Contract):
    label: OptionLabel
    product_type: ProductType
    units: int
    unit_sqft: int
    gfa_sqft: float
    relief: list[str]  # "type (code section)", e.g. "variance (903.03)"; empty = by right
    margin: Range  # on cost
    months: Range  # to permit-ready
    approval_prob: Range
    max_land_price: Range
    score: Range
    revenue_basis: str  # comps or rent basis, in words
    entitlement_basis: list[str]  # where the approval odds come from


class Step(Contract):
    order: int
    action: str
    who: str
    cost_usd: Interval  # (0, 0) = free
    why: str
    flag_ids: list[str]


class ScoreItem(Contract):
    """Counterfactual: points the score would regain without this driver."""

    component: ComponentKey
    points_lost: float
    driver_flag_id: str  # a flag id, or "relief:<type>+<type>"


class Assumption(Contract):
    key: str  # also the override key accepted by the engine
    label: str
    value: float
    unit: str
    source: str  # "PLACEHOLDER ..." until replaced by a benchmark or calibration
    editable: bool
    min: float | None
    max: float | None


class LotDimensions(Contract):
    width: float
    depth: float


class RulesSummary(Contract):
    scenario: Literal["strict", "contextual"] | None  # contextual = 925.06.C side setbacks
    confidence: Confidence | None
    neighbors_built: bool | None
    lot_dimensions_ft: LotDimensions | None


class Versions(Contract):
    engine: str
    ruleset: str
    schema_: str = Field(alias="schema")
    data_as_of: date | None  # oldest source date among the inputs


class CheckResult(Contract):
    """One zoning rule applied to one building. Rules pass or fail; probability enters only
    through the approval (`relief_type`) that can fix a failure."""

    check_id: str  # use_allowed | min_lot_size | fits_envelope | row_fits_width | subdivision
    label: str
    section: str | None  # zoning code section
    status: Literal["pass", "needs_approval", "rejected", "not_applicable"]
    required: float | None  # what the rule requires (sf or ft)
    provided: float | None  # what this lot/building provides
    unit: str | None
    relief_type: str | None  # approval that fixes it, or implausible / use_variance
    note: str | None


class SiteCheck(Contract):
    """Overlay rules that apply to the site whatever is built."""

    check_id: str
    label: str
    section: str
    status: Literal["applies", "clear", "unknown"]
    note: str | None


class NotChecked(Contract):
    label: str
    section: str
    reason: str


class ProgramEvaluation(Contract):
    product_type: ProductType
    units: int
    gfa_sqft: float
    outcome: Literal["by_right", "needs_approval", "rejected"]
    checks: list[CheckResult]
    approval_prob: Range | None  # product of the needed approvals' odds; None if rejected
    approval_months: Range | None
    representative: bool  # one column per building type for display
    chosen_as: OptionLabel | None  # this program is options[] by_right / with_relief


class RuleChecks(Contract):
    """Every building type tested on this lot, rule by rule ("why this score")."""

    district: str
    scenario: Literal["strict", "contextual"]
    uncovered_districts: list[str]
    site_checks: list[SiteCheck]
    not_checked: list[NotChecked]
    programs: list[ProgramEvaluation]
    odds_note: str


class SiteAnalysis(Contract):
    verdict: Verdict
    narrative: Narrative
    metrics: Metrics | None  # None when no program could be evaluated
    flags: list[Flag]  # worst first
    cleared: list[str]  # checks that came back clean
    options: list[ProgramOption]  # best by-right and best with relief (0-2)
    next_steps: list[Step]  # free first, then cheapest deal-killer
    score_breakdown: list[ScoreItem]
    rule_checks: RuleChecks | None = None  # None when zoning is not covered
    assumptions: list[Assumption]
    rules: RulesSummary
    versions: Versions
