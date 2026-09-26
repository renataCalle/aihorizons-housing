import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { toEvidence, toSiteReport } from './adapters'

function fixture(name: string): unknown {
  const url = new URL(`../../../fixtures/mock/ui-draft/${name}`, import.meta.url)
  return JSON.parse(readFileSync(url, 'utf8'))
}

describe('toSiteReport', () => {
  const raw = fixture('sample_lot_a.analysis.json') as Record<string, any>
  const report = toSiteReport(raw)

  it('maps the parcel and verdict', () => {
    expect(report.parcel.id).toBe('0000-X-00000-0000-00')
    expect(report.parcel.name).toBe('Sample lot A')
    expect(report.verdict.headline).toBe(raw.verdict.headline)
    expect(report.illustrative).toBe(true)
  })

  it('maps low/high ranges to p10/p90 with no p50', () => {
    expect(report.verdict.scoreRange).toEqual({
      p10: raw.verdict.score_range.low,
      p50: null,
      p90: raw.verdict.score_range.high,
      unit: raw.verdict.score_range.unit,
    })
  })

  it('keeps every array item, in order', () => {
    expect(report.findings.map((f) => f.id)).toEqual(raw.findings.map((f: any) => f.id))
    expect(report.scoreComponents).toHaveLength(raw.score_breakdown.length)
    expect(report.nextSteps.map((s) => s.order)).toEqual(raw.next_steps.map((s: any) => s.order))
    expect(report.assumptions).toHaveLength(raw.assumptions.length)
  })

  it('stamps versions', () => {
    expect(report.versions).toEqual({
      engine: raw.meta.engine_version,
      ruleset: raw.meta.rules_version,
      schema: raw.meta.contract_version,
      dataAsOf: raw.meta.data_refreshed,
    })
  })

  it('shows an unrecognized severity or band as unknown, never clear', () => {
    const odd = structuredClone(raw)
    odd.findings[0].severity = 'something_new'
    odd.verdict.band = 'something_new'
    const mapped = toSiteReport(odd)
    expect(mapped.findings[0].severity).toBe('unknown')
    expect(mapped.verdict.band).toBe('unknown')
  })

  it('links the approvals option to its evidence', () => {
    expect(report.bestWithApprovals?.evidenceId).toBe(raw.best_with_approvals.evidence_id)
    expect(report.bestWithApprovals?.precedent).toEqual({
      granted: raw.best_with_approvals.precedent_granted,
      total: raw.best_with_approvals.precedent_total,
    })
  })
})

describe('toEvidence', () => {
  it('maps cases and the code reference', () => {
    const raw = fixture('ev-variance-4-townhomes.evidence.json') as Record<string, any>
    const evidence = toEvidence(raw)
    expect(evidence.id).toBe(raw.id)
    expect(evidence.cases).toHaveLength(raw.cases.length)
    expect(evidence.code?.section).toBe(raw.code.section)
  })
})
