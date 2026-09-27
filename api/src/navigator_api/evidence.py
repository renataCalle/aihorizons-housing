"""The evidence drawer: one finding or the approvals option of a lot's report.

Formatting only. Every severity, range, resolution and rule result is the engine's
(SiteAnalysis); dates and zoning board cases are the stored facts (SiteContext). Evidence IDs
are scoped to one lot's report: `flag.<flag id>` for a finding, `option.with_relief` for the
approvals option in "What you can build".
"""

from statistics import median

from navigator_api.models import Case, EvidenceDetail, EvidenceSource, Outcome, Precedent
from navigator_contracts import SiteAnalysis, SiteContext
from navigator_contracts.site_analysis import Evidence, Flag
from navigator_contracts.site_context import ZbaCase

# Pittsburgh's code of ordinances; the engine cites sections, not per-section links.
CODE_URL = "https://library.municode.com/pa/pittsburgh/codes/code_of_ordinances"

FAILING = ("needs_approval", "rejected")

OUTCOME: dict[str, Outcome] = {
    "approved": "granted",
    "approved_with_conditions": "granted",
    "denied": "denied",
    "withdrawn": "withdrawn",
    "continued": "pending",
    "unknown": "unknown",
}


def build_evidence(
    evidence_id: str,
    parcel_id: str,
    analysis: SiteAnalysis,
    context: SiteContext | None,
    illustrative: bool,
    mock_precedent: Precedent | None = None,
) -> EvidenceDetail | None:
    """None when the report has no such finding or option. `illustrative` marks a generated
    lot; only those get `mock_precedent` in place of real zoning board decisions."""
    kind, _, key = evidence_id.partition(".")
    if kind == "flag":
        flag = next((f for f in analysis.flags if f.id == key), None)
        return flag and _finding(evidence_id, parcel_id, flag, analysis, context, illustrative)
    if kind == "option" and key == "with_relief":
        precedent = mock_precedent if illustrative and mock_precedent else _precedent(context)
        return _approvals(evidence_id, parcel_id, analysis, precedent, illustrative)
    return None


def _finding(
    evidence_id: str,
    parcel_id: str,
    flag: Flag,
    analysis: SiteAnalysis,
    context: SiteContext | None,
    illustrative: bool,
) -> EvidenceDetail:
    sources = [_source(e, context) for e in flag.evidence]
    return EvidenceDetail(
        id=evidence_id,
        kind="finding",
        parcel_id=parcel_id,
        title=flag.title,
        category=flag.category,
        severity=flag.severity,
        confidence=flag.confidence,
        cost_usd=flag.cost_usd,
        months=flag.months,
        sources=sources,
        code_url=CODE_URL if any(s.code_section for s in sources) else None,
        how_to_resolve=flag.resolution,
        resolved_by=next(
            (s for s in analysis.next_steps if s.order == flag.resolved_by_step), None
        ),
        illustrative=illustrative,
        versions=analysis.versions,
    )


def _approvals(
    evidence_id: str,
    parcel_id: str,
    analysis: SiteAnalysis,
    precedent: Precedent,
    illustrative: bool,
) -> EvidenceDetail | None:
    option = next((o for o in analysis.options if o.label == "with_relief"), None)
    if option is None:
        return None
    rc = analysis.rule_checks
    program = next((p for p in rc.programs if p.chosen_as == "with_relief"), None) if rc else None
    checks = [c for c in program.checks if c.status in FAILING] if program else []
    return EvidenceDetail(
        id=evidence_id,
        kind="approvals",
        parcel_id=parcel_id,
        title=None,
        product_type=option.product_type,
        units=option.units,
        category="zoning",
        months_to_permit=option.months,
        approval_prob=option.approval_prob,
        approval_months=program.approval_months if program else None,
        relief=option.relief,
        entitlement_basis=option.entitlement_basis,
        odds_note=rc.odds_note if rc else None,
        rule_checks=checks,
        code_url=CODE_URL if any(c.section for c in checks) else None,
        how_to_resolve=None,
        resolved_by=None,
        precedent=precedent,
        illustrative=illustrative,
        versions=analysis.versions,
    )


def _source(e: Evidence, context: SiteContext | None) -> EvidenceSource:
    """The flag's citation. A flag without a date takes its layer's as-of date."""
    stored = context.provenance.get(e.layer) if context and e.layer else None
    dated_by_layer = e.as_of is None and stored is not None and stored.as_of is not None
    return EvidenceSource(
        source=e.source,
        as_of=stored.as_of if dated_by_layer and stored else e.as_of,
        as_of_from_provenance=dated_by_layer,
        layer=e.layer,
        code_section=e.code_section,
        url=e.url,
    )


def _precedent(context: SiteContext | None) -> Precedent:
    cases = context.zba_cases_nearby if context else None
    if cases is None:
        stored = context.provenance.get("zba_cases") if context else None
        return Precedent(status="unavailable", note=stored.note if stored else None)
    rows = [_case(c) for c in sorted(cases, key=lambda c: c.distance_ft or float("inf"))]
    months = [c.months_to_decision for c in rows if c.months_to_decision is not None]
    return Precedent(
        status="available",
        granted=sum(c.outcome == "granted" for c in rows),
        total=len(rows),
        median_months=round(median(months), 1) if months else None,
        cases=rows,
    )


def _case(c: ZbaCase) -> Case:
    return Case(
        case_id=c.case_id,
        area=c.district,
        request=", ".join(c.relief_types) or None,
        outcome=OUTCOME[c.outcome],
        months_to_decision=round(c.days_to_decision / 30.44, 1)
        if c.days_to_decision is not None
        else None,
        source_url=c.url,
    )
