/**
 * The only module that knows the API's shapes (types.gen.ts, enforced by oxlint).
 * When the contracts change, regenerate the types and fix the mapping here; components
 * only see the view models in src/models/.
 */
import type { Estimate, Interval } from '../models/estimate'
import type { Evidence } from '../models/evidence'
import type { Health } from '../models/health'
import type { MapBand, MapFeatureKind, MapFeatures, ParcelLayer } from '../models/map'
import type { Analysis, Band, Parcel, Severity, SiteReport, Versions } from '../models/report'
import type { LookupResult } from '../models/search'
import type { components } from './types.gen'

type S = components['schemas']

const BANDS: Record<string, Band> = {
  fast_track: 'fast_track',
  feasible_with_conditions: 'conditions',
  high_risk: 'high_risk',
  not_scored: 'unknown',
}

const SEVERITIES: Record<string, Severity> = {
  high: 'deal_risk',
  medium: 'caution',
  low: 'minor',
  unknown: 'unknown',
}

/** An unrecognized band or severity is shown as unknown, never as clear. */
export function toBand(value: string): Band {
  return BANDS[value] ?? 'unknown'
}

export function toSeverity(value: string): Severity {
  return SEVERITIES[value] ?? 'unknown'
}

function toEstimate(range: S['Range']): Estimate {
  return { p10: range.p10, p50: range.p50, p90: range.p90 }
}

function toInterval(pair: [number, number] | null): Interval | null {
  return pair ? { low: pair[0], high: pair[1] } : null
}

function toVersions(v: S['Versions']): Versions {
  return { engine: v.engine, ruleset: v.ruleset, schema: v.schema, dataAsOf: v.data_as_of }
}

export function toParcel(p: S['ParcelSummary']): Parcel {
  return {
    id: p.parcel_id,
    blockLot: p.block_lot,
    name: p.display_name,
    address: p.address,
    municipality: p.municipality,
    neighborhood: p.neighborhood,
    zoning: p.zoning,
    lotAreaSqft: p.lot_area_sqft,
    currentUse: p.current_use,
    ownerType: p.owner_type,
    assessedLand: p.assessed_land,
    centroid: p.centroid,
    candidate: p.candidate,
    illustrative: p.illustrative,
    assemblyId: p.assembly_id ?? null,
    score: p.score ?? null,
    band: p.band ? toBand(p.band) : null,
    topFlag: p.top_flag
      ? { title: p.top_flag, severity: toSeverity(p.top_flag_severity ?? 'unknown') }
      : null,
    maxLandPrice: p.max_land_price ? toEstimate(p.max_land_price) : null,
    leadOption: p.lead_option
      ? {
          label: p.lead_option.label,
          productType: p.lead_option.product_type,
          units: p.lead_option.units,
          relief: p.lead_option.relief,
        }
      : null,
  }
}

export function toAnalysis(a: S['SiteAnalysis']): Analysis {
  const m = a.metrics
  return {
    verdict: {
      band: toBand(a.verdict.band),
      score: a.verdict.score,
      scoreRange: a.verdict.score_range ? toEstimate(a.verdict.score_range) : null,
      headline: a.narrative.summary ?? a.verdict.headline,
      landRisk: a.verdict.land_risk,
    },
    scoreComponents: a.verdict.components.map((c) => ({
      key: c.key,
      label: c.label,
      points: c.points,
      maxPoints: c.max_points,
      note: c.note,
    })),
    metrics: m
      ? {
          option: m.option,
          monthsToPermitReady: toEstimate(m.months_to_permit),
          approvalProbability: toEstimate(m.approval_prob),
          maxLandPrice: toEstimate(m.max_land_price),
          landBasis: { value: m.land_basis.value, source: m.land_basis.source },
          siteCostPremium: {
            low: m.site_cost_premium.low,
            high: m.site_cost_premium.high,
            drivers: m.site_cost_premium.drivers,
          },
          landOverMax: m.land_over_max
            ? { low: m.land_over_max.low, high: m.land_over_max.high }
            : null,
          comps: {
            count: m.comps.count,
            radiusMi: m.comps.radius_mi,
            windowMonths: m.comps.window_months,
          },
        }
      : null,
    flags: a.flags.map((f) => ({
      id: f.id,
      category: f.category,
      severity: toSeverity(f.severity),
      title: f.title,
      cost: toInterval(f.cost_usd),
      months: toInterval(f.months),
      evidence: f.evidence.map((e) => ({
        source: e.source,
        asOf: e.as_of,
        layer: e.layer,
        codeSection: e.code_section,
        url: e.url,
      })),
      confidence: f.confidence,
      resolution: f.resolution,
      resolvedByStep: f.resolved_by_step,
    })),
    cleared: a.cleared,
    options: a.options.map((o) => ({
      label: o.label,
      productType: o.product_type,
      units: o.units,
      unitSqft: o.unit_sqft,
      gfaSqft: o.gfa_sqft,
      relief: o.relief,
      margin: toEstimate(o.margin),
      monthsToPermitReady: toEstimate(o.months),
      approvalProbability: toEstimate(o.approval_prob),
      maxLandPrice: toEstimate(o.max_land_price),
      revenueBasis: o.revenue_basis,
      entitlementBasis: o.entitlement_basis,
    })),
    nextSteps: a.next_steps.map((s) => ({
      order: s.order,
      action: s.action,
      who: s.who,
      cost: { low: s.cost_usd[0], high: s.cost_usd[1] },
      why: s.why,
      flagIds: s.flag_ids,
    })),
    assumptions: a.assumptions.map((x) => ({
      key: x.key,
      label: x.label,
      value: x.value,
      unit: x.unit,
      source: x.source,
      placeholder: x.source.startsWith('PLACEHOLDER'),
      editable: x.editable,
      min: x.min,
      max: x.max,
    })),
    versions: toVersions(a.versions),
  }
}

export function toSiteReport(data: unknown): SiteReport {
  const r = data as S['ParcelReport']
  return { parcel: toParcel(r.parcel), analysis: r.analysis ? toAnalysis(r.analysis) : null }
}

export function toParcelLayer(data: unknown): ParcelLayer {
  const fc = data as S['ParcelFeatureCollection']
  return {
    type: 'FeatureCollection',
    features: fc.features.map((f) => {
      const p = f.properties
      const band: MapBand = !p.candidate ? 'none' : p.band ? toBand(p.band) : 'unknown'
      return {
        type: 'Feature',
        id: p.parcel_id,
        geometry: f.geometry as unknown as GeoJSON.Geometry,
        properties: {
          id: p.parcel_id,
          name: p.display_name,
          band,
          score: p.score,
          rank: p.rank ?? null,
          assemblyId: p.assembly_id ?? null,
        },
      }
    }),
  }
}

export function toMapFeatures(data: unknown): MapFeatures {
  const fc = data as S['MapFeatureCollection']
  return {
    type: 'FeatureCollection',
    features: fc.features.map((f) => ({
      type: 'Feature',
      geometry: f.geometry as unknown as GeoJSON.Geometry,
      properties: { kind: f.properties.kind as MapFeatureKind, name: f.properties.name ?? null },
    })),
  }
}

export function toEvidence(data: unknown): Evidence {
  const e = data as S['EvidenceDetail']
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
    precedent:
      e.precedent_granted != null && e.precedent_total != null
        ? { granted: e.precedent_granted, total: e.precedent_total }
        : null,
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

export function toLookup(data: unknown): LookupResult {
  const r = data as S['LookupResponse']
  return {
    kind: r.kind,
    format: r.format ?? null,
    matches: r.matches.map((m) => ({ matchedOn: m.matched_on, parcel: toParcel(m.parcel) })),
  }
}

export function toHealth(data: unknown): Health {
  const h = data as S['Health']
  return {
    ok: (h.status ?? 'ok') === 'ok',
    siteSource: h.site_source,
    illustrative: h.illustrative,
    parcels: h.parcels,
    versions: toVersions(h.versions),
  }
}
