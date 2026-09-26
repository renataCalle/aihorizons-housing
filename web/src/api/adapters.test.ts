import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { toBand, toEvidence, toParcelLayer, toSeverity, toSiteReport } from './adapters'

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

describe('toEvidence', () => {
  it('maps cases and the code reference', () => {
    const raw = json('mock/ui-draft/ev-variance-4-townhomes.evidence.json')
    const evidence = toEvidence(raw)
    expect(evidence.id).toBe(raw.id)
    expect(evidence.cases).toHaveLength(raw.cases.length)
    expect(evidence.code?.section).toBe(raw.code.section)
  })
})
