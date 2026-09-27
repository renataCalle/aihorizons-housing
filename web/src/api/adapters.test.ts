import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  toAreaSummary,
  toBand,
  toEvidence,
  toParcelLayer,
  toSeverity,
  toSiteReport,
} from './adapters'

const FIXTURES = new URL('../../../fixtures/', import.meta.url)

function json(path: string): any {
  return JSON.parse(readFileSync(new URL(path, FIXTURES), 'utf8'))
}

const summaries: any[] = json('mock/generated/summaries.json')
const sampleSummary = summaries.find((s) => s.display_name === 'Sample lot A')
const sampleAnalysis = json(`mock/generated/site_analysis/${sampleSummary.parcel_id}.json`)

describe('toBand and toSeverity', () => {
  it("maps the engine's names to the UI's", () => {
    expect(toBand('feasible_with_conditions')).toBe('conditions')
    expect(toBand('not_scored')).toBe('unknown')
    expect(toSeverity('high')).toBe('deal_risk')
    expect(toSeverity('medium')).toBe('caution')
    expect(toSeverity('low')).toBe('minor')
  })

  it('shows anything unrecognized as unknown, never clear', () => {
    expect(toBand('something_new')).toBe('unknown')
    expect(toSeverity('something_new')).toBe('unknown')
  })
})

describe('toSiteReport', () => {
  const report = toSiteReport({ parcel: sampleSummary, analysis: sampleAnalysis })

  it('maps the parcel header', () => {
    expect(report.parcel.id).toBe('0000X00000000000')
    expect(report.parcel.name).toBe('Sample lot A')
    expect(report.parcel.illustrative).toBe(true)
    expect(report.parcel.centroid).toHaveLength(2)
  })

  it('keeps p10/p50/p90 estimates', () => {
    expect(report.analysis?.verdict.scoreRange).toEqual(sampleAnalysis.verdict.score_range)
  })

  it('keeps every array item, in order', () => {
    const a = report.analysis!
    expect(a.flags.map((f) => f.id)).toEqual(sampleAnalysis.flags.map((f: any) => f.id))
    expect(a.scoreComponents).toHaveLength(sampleAnalysis.verdict.components.length)
    expect(a.nextSteps.map((s) => s.order)).toEqual(
      sampleAnalysis.next_steps.map((s: any) => s.order),
    )
    expect(a.options).toHaveLength(sampleAnalysis.options.length)
    expect(a.assumptions).toHaveLength(sampleAnalysis.assumptions.length)
  })

  it('turns [low, high] pairs into intervals', () => {
    const step = sampleAnalysis.next_steps[0]
    expect(report.analysis!.nextSteps[0].cost).toEqual({
      low: step.cost_usd[0],
      high: step.cost_usd[1],
    })
  })

  it('stamps versions', () => {
    expect(report.analysis!.versions.schema).toBe(sampleAnalysis.versions.schema)
  })

  it('handles a parcel with no analysis', () => {
    const other = summaries.find((s) => !s.candidate)
    const empty = toSiteReport({ parcel: other, analysis: null })
    expect(empty.analysis).toBeNull()
    expect(empty.parcel.band).toBeNull()
  })

  it('reads a real golden analysis', () => {
    const golden = summaries.find((s) => s.parcel_id === '0055A00137000000')
    const analysis = json('golden/site_analysis/steep_slope.json')
    const r = toSiteReport({ parcel: golden, analysis })
    expect(r.parcel.illustrative).toBe(false)
    expect(r.analysis!.flags[0].severity).toBe('deal_risk')
  })
})

describe('toParcelLayer', () => {
  it('marks non-candidates as outline-only and keeps feature ids', () => {
    const layer = toParcelLayer({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [0, 0] },
          properties: { parcel_id: 'a', display_name: 'A', candidate: false, band: null, score: null },
        },
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [0, 0] },
          properties: {
            parcel_id: 'b',
            display_name: 'B',
            candidate: true,
            band: 'not_scored',
            score: null,
          },
        },
      ],
    })
    expect(layer.features.map((f) => f.properties.band)).toEqual(['none', 'unknown'])
    expect(layer.features[0].id).toBe('a')
  })
})

const versions = {
  engine: '0.1.0',
  ruleset: 'rules drafts 2026-09-26',
  schema: '0.1.0',
  data_as_of: '2018-07-27',
  ruleset_as_of: '2026-09-26',
}

// Trimmed from GET /api/parcels/0055A00137000000/evidence/flag.steep_slope
const steepSlope = {
  id: 'flag.steep_slope',
  kind: 'finding',
  parcel_id: '0055A00137000000',
  title: '84% of lot on 25%+ slope',
  category: 'physical',
  severity: 'high',
  confidence: 'medium',
  cost_usd: [40000, 150000],
  months: [1, 4],
  sources: [
    {
      source: '25% or Greater Slope',
      as_of: '2026-09-23',
      as_of_from_provenance: false,
      layer: 'steep_slope',
      code_section: '915.02',
      url: 'https://data.wprdc.org/slopes.geojson',
    },
  ],
  code_sections: [
    {
      section: '915.02',
      title: 'Environmental Standards',
      summary: 'Sets grading, cut-and-fill and retaining wall rules.',
      url: 'https://ecode360.com/PI6865',
      as_of: '2026-09-26',
      effective: '2005-12-30',
    },
  ],
  how_to_resolve: 'Geotechnical report; walls under 10 ft, cut/fill under 25% (915.02)',
  resolved_by: {
    order: 3,
    action: 'Geotechnical and grading feasibility study',
    who: 'geotechnical engineer',
    cost_usd: [3000, 8000],
    why: 'Geotechnical report',
    flag_ids: ['steep_slope'],
  },
  precedent: null,
  illustrative: false,
  versions,
}

// Trimmed from GET /api/parcels/0055A00137000000/evidence/option.with_relief
const approvals = {
  id: 'option.with_relief',
  kind: 'approvals',
  parcel_id: '0055A00137000000',
  title: null,
  product_type: 'townhome',
  units: 2,
  category: 'zoning',
  months_to_permit: { p10: 8, p50: 9.5, p90: 11.1 },
  approval_prob: { p10: 0.66, p50: 0.73, p90: 0.81 },
  approval_months: { p10: 4.9, p50: 6.1, p90: 7.5 },
  relief: ['special_exception (911.04.A.69A)', 'subdivision (911.02 (own lot per unit))'],
  entitlement_basis: ['special_exception: PLACEHOLDER prior (ZBA)'],
  odds_note: 'Each rule either passes or fails.',
  rule_checks: [
    {
      check_id: 'use_allowed',
      label: 'Housing type allowed in the district',
      section: '911.04.A.69A',
      status: 'needs_approval',
      required: null,
      provided: null,
      unit: null,
      relief_type: 'special_exception',
      note: "single_unit_attached is 'S' in R1D-M",
    },
  ],
  sources: [],
  code_sections: [
    {
      section: '915.02',
      title: 'Environmental Standards',
      summary: 'Sets grading, cut-and-fill and retaining wall rules.',
      url: 'https://ecode360.com/PI6865',
      as_of: '2026-09-26',
      effective: '2005-12-30',
    },
  ],
  how_to_resolve: null,
  resolved_by: null,
  precedent: {
    status: 'unavailable',
    note: 'Not available: pittsburghpa.gov blocks this client (HTTP 403).',
    granted: null,
    total: null,
    median_months: null,
    cases: [],
    ai_extracted: false,
  },
  illustrative: false,
  versions,
}

describe('toEvidence', () => {
  it("maps a finding's judgments, source and resolving step", () => {
    const e = toEvidence(steepSlope)
    expect(e.kind).toBe('finding')
    expect(e.severity).toBe('deal_risk')
    expect(e.cost).toEqual({ low: 40000, high: 150000 })
    expect(e.sources[0]).toMatchObject({ codeSection: '915.02', asOf: '2026-09-23' })
    expect(e.resolvedBy).toMatchObject({ order: 3, cost: { low: 3000, high: 8000 } })
    expect(e.codeSections[0]).toMatchObject({ section: '915.02', effective: '2005-12-30' })
    expect(e.versions.rulesetAsOf).toBe('2026-09-26')
    expect(e.program).toBeNull()
    expect(e.precedent).toBeNull()
  })

  it('maps the approvals option with its failing rules and no zoning board cases', () => {
    const e = toEvidence(approvals)
    expect(e.program).toEqual({ productType: 'townhome', units: 2 })
    expect(e.severity).toBeNull()
    expect(e.ruleChecks[0]).toMatchObject({ id: 'use_allowed', relief: 'special_exception' })
    expect(e.approvalProbability?.p10).toBe(0.66)
    expect(e.precedent).toMatchObject({ status: 'unavailable', cases: [], granted: null })
  })

  it('maps zoning board cases with their dates, approval types and no link', () => {
    const e = toEvidence({
      ...approvals,
      precedent: {
        status: 'available',
        note: null,
        rule: 'Same zoning board approval type',
        source: 'Zoning Board of Adjustment decisions',
        as_of: '2026-08-28',
        nearby: 4,
        granted: 1,
        total: 1,
        median_months: 3.1,
        cases: [
          {
            case_id: '134 of 2025',
            area: 'R1D-M',
            request: null,
            relief_types: ['variance'],
            decided: '2025-11-03',
            outcome: 'granted',
            months_to_decision: 3.1,
            source_url: null,
          },
        ],
        ai_extracted: false,
      },
    })
    expect(e.precedent).toMatchObject({ status: 'available', nearby: 4, asOf: '2026-08-28' })
    expect(e.precedent?.cases[0]).toMatchObject({
      reliefTypes: ['variance'],
      decided: '2025-11-03',
      sourceUrl: null,
    })
  })
})

describe('toAreaSummary', () => {
  it("maps the engine's bands to the UI's, with zero for bands not present", () => {
    const summary = toAreaSummary({
      lots: 3,
      ranked_for: { type: 'townhome', units: null },
      bands: { feasible_with_conditions: 1, high_risk: 1, not_scored: 1 },
      blockers: [{ driver: 'steep_slope', label: 'Steep slope', lots: 2, avg_points: 9.3 }],
      near_misses: 4,
      assemblies: 0,
    })
    expect(summary.bands).toEqual({ fast_track: 0, conditions: 1, high_risk: 1, unknown: 1 })
    expect(summary.blockers[0]).toEqual({
      driver: 'steep_slope',
      label: 'Steep slope',
      lots: 2,
      avgPoints: 9.3,
    })
    expect(summary.rankedFor).toEqual({ type: 'townhome', units: null })
  })
})
