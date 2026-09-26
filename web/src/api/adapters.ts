/**
 * The only module that knows the API's shapes (types.gen.ts, enforced by oxlint).
 * When the contracts change, regenerate the types and fix the mapping here; components
 * only see the view models in src/models/.
 */
import type { Estimate } from '../models/estimate'
import type { Evidence } from '../models/evidence'
import type { Health } from '../models/health'
import type { Band, Finding, ProgramOption, Severity, SiteReport, Source } from '../models/report'
import type { components } from './types.gen'

type S = components['schemas']

const BANDS: readonly Band[] = ['fast_track', 'conditions', 'high_risk', 'unknown']
const SEVERITIES: readonly Severity[] = ['deal_risk', 'caution', 'unknown']

/** An unrecognized band or severity is shown as unknown, never as clear. */
function oneOf<T extends string>(allowed: readonly T[], value: string): T | 'unknown' {
  return (allowed as readonly string[]).includes(value) ? (value as T) : 'unknown'
}

/** The provisional API sends low/high, which are p10/p90. p50 arrives with the real contracts. */
export function toEstimate(range: S['Range']): Estimate {
  return { p10: range.low, p50: null, p90: range.high, unit: range.unit }
}

function toEstimateOrNull(range: S['Range'] | null | undefined): Estimate | null {
  return range ? toEstimate(range) : null
}

function toSource(source: S['SourceRef']): Source {
  return {
    label: source.label,
    dataset: source.dataset,
    asOf: source.as_of ?? null,
    url: source.url ?? null,
  }
}

function toPrecedent(granted?: number | null, total?: number | null) {
  return granted != null && total != null ? { granted, total } : null
}

function toProgram(option: S['ProgramOption'] | null | undefined): ProgramOption | null {
  if (!option) return null
  return {
    product: option.product,
    units: option.units,
    sqftEach: option.sqft_each ?? null,
    tenure: option.tenure ?? 'for_sale',
    margin: toEstimate(option.margin_pct),
    monthsToPermitReady: toEstimate(option.months_to_permit_ready),
    approvalPath: option.approval_path,
    relief: option.relief ?? [],
    codeBasis: option.code_basis ?? null,
    precedent: toPrecedent(option.precedent_granted, option.precedent_total),
    evidenceId: option.evidence_id ?? null,
  }
}

function toFinding(finding: S['Finding']): Finding {
  return {
    id: finding.id,
    severity: oneOf(SEVERITIES, finding.severity),
    title: finding.title,
    detail: finding.detail,
    impactCost: toEstimateOrNull(finding.impact_cost),
    impactMonths: toEstimateOrNull(finding.impact_months),
    impactLabel: finding.impact_label,
    sources: finding.sources.map(toSource),
    confidence: finding.confidence,
    confidenceNote: finding.confidence_note ?? null,
    resolvedByStep: finding.resolved_by_step ?? null,
    evidenceId: finding.evidence_id ?? null,
  }
}

export function toSiteReport(data: unknown): SiteReport {
  const a = data as S['SiteAnalysis']
  const p = a.parcel
  const h = a.headline_numbers
  return {
    parcel: {
      id: p.parcel_id,
      blockLot: null,
      name: p.display_name,
      address: p.address ?? null,
      neighborhood: p.neighborhood,
      zoningDistrict: p.zoning_district,
      lotAreaSqft: p.lot_area_sqft,
      currentUse: p.current_use,
      ownerType: p.owner_type,
      assessedValue: p.assessed_value ?? null,
      listedPrice: p.listed_price ?? null,
      centroid: p.centroid,
      score: p.score ?? null,
      band: oneOf(BANDS, p.band),
    },
    verdict: {
      band: oneOf(BANDS, a.verdict.band),
      score: a.verdict.score ?? null,
      scoreRange: toEstimateOrNull(a.verdict.score_range),
      headline: a.verdict.headline,
    },
    scoreComponents: a.score_breakdown.map((c) => ({
      key: c.key,
      label: c.label,
      points: c.points,
      maxPoints: c.max_points,
      note: c.note,
    })),
    headline: {
      approvalPath: h.approval_path,
      approvalProbability: null,
      approvalSummary: h.approval_summary,
      monthsToPermitReady: toEstimate(h.months_to_permit_ready),
      siteCostPremium: toEstimate(h.site_cost_premium),
      siteCostSummary: h.site_cost_summary,
      maxLandPrice: toEstimate(h.max_land_price),
      targetMarginPct: h.target_margin_pct,
      listedPrice: h.listed_price ?? null,
      comps: {
        count: h.comps_count,
        radiusMi: h.comps_radius_mi,
        windowMonths: h.comps_window_months,
      },
    },
    findings: a.findings.map(toFinding),
    cleared: a.cleared.map((c) => ({
      label: c.label,
      source: c.source ? toSource(c.source) : null,
    })),
    bestByRight: toProgram(a.best_by_right),
    bestWithApprovals: toProgram(a.best_with_approvals),
    nextSteps: a.next_steps.map((s) => ({
      order: s.order,
      title: s.title,
      why: s.why,
      who: s.who,
      cost: toEstimate(s.cost),
      durationLabel: s.duration_label,
    })),
    assumptions: a.assumptions.map((x) => ({
      key: x.key,
      label: x.label,
      value: typeof x.value === 'object' ? toEstimate(x.value) : x.value,
      sourceLabel: x.source_label,
      editable: x.editable ?? true,
    })),
    versions: {
      engine: a.meta.engine_version,
      ruleset: a.meta.rules_version,
      schema: a.meta.contract_version ?? '',
      dataAsOf: a.meta.data_refreshed,
    },
    illustrative: a.meta.illustrative ?? false,
  }
}

export function toEvidence(data: unknown): Evidence {
  const e = data as S['Evidence']
  return {
    id: e.id,
    kind: e.kind,
    title: e.title,
    appliesTo: e.applies_to,
    code: e.code
      ? {
          section: e.code.section,
          asOf: e.code.as_of,
          summary: e.code.summary,
          url: e.code.url ?? null,
        }
      : null,
    precedent: toPrecedent(e.precedent_granted, e.precedent_total),
    medianMonths: e.median_months ?? null,
    cases: (e.cases ?? []).map((c) => ({
      id: c.case_id,
      neighborhood: c.neighborhood,
      request: c.request,
      outcome: c.outcome,
      monthsToDecision: c.months_to_decision ?? null,
      sourceUrl: c.source_url ?? null,
    })),
    aiExtracted: e.ai_extracted ?? false,
    confidence: e.confidence,
    confidenceNote: e.confidence_note,
    howToResolve: e.how_to_resolve,
  }
}

export function toHealth(data: unknown): Health {
  const h = data as S['Health']
  return {
    ok: (h.status ?? 'ok') === 'ok',
    siteSource: h.site_source,
    illustrative: h.illustrative,
    versions: {
      engine: h.versions.engine,
      ruleset: h.versions.ruleset,
      schema: h.versions.schema_version,
      dataAsOf: h.versions.data_as_of,
    },
  }
}
