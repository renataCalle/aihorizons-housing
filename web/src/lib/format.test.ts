import { describe, expect, it } from 'vitest'
import type { Estimate } from '../models/estimate'
import { formatRange } from './format'

const est = (p10: number, p90: number, unit: Estimate['unit']): Estimate => ({
  p10,
  p50: null,
  p90,
  unit,
})

describe('formatRange', () => {
  it('formats money as a k range', () => {
    expect(formatRange(est(24_000, 41_000, 'usd'))).toBe('$24k–$41k')
  })

  it('says Free for a no-cost range', () => {
    expect(formatRange(est(0, 0, 'usd'))).toBe('Free')
  })

  it('formats months', () => {
    expect(formatRange(est(5, 7, 'months'))).toBe('5–7 months')
  })

  it('formats score points without a unit', () => {
    expect(formatRange(est(66, 78, 'points'))).toBe('66–78')
  })
})
