import { describe, expect, it } from 'vitest'
import {
  formatAssumption,
  formatAssumptionRange,
  formatMaxLand,
  formatMonthYear,
  formatMoneyRange,
  formatMonthsRange,
  formatNumberRange,
  formatPercentRange,
  formatSqft,
} from './format'

describe('format', () => {
  it('formats money as a k range', () => {
    expect(formatMoneyRange({ low: 24_000, high: 41_000 })).toBe('$24k–$41k')
  })

  it('says Free for a no-cost span', () => {
    expect(formatMoneyRange({ low: 0, high: 0 })).toBe('Free')
  })

  it('keeps the sign on negative values', () => {
    expect(formatMoneyRange({ low: -120_000, high: -40_000 })).toBe('-$120k–-$40k')
  })

  it('formats months, rounding to whole months', () => {
    expect(formatMonthsRange({ low: 4.6, high: 7.2 })).toBe('5–7 months')
  })

  it('formats score ranges', () => {
    expect(formatNumberRange({ low: 56.4, high: 67.8 })).toBe('56–68')
  })

  it('formats lot area', () => {
    expect(formatSqft(3960.4)).toBe('3,960 sq ft')
  })

  it('says when no land price works', () => {
    expect(formatMaxLand({ low: -520_000, high: -254_000 })).toBe('None at target margin')
    expect(formatMaxLand({ low: -5_000, high: 41_000 })).toBe('Up to $41k')
    expect(formatMaxLand({ low: 24_000, high: 41_000 })).toBe('$24k–$41k')
  })

  it('formats margins as a percent range', () => {
    expect(formatPercentRange({ low: -0.5157, high: -0.3236 })).toBe('-52% to -32%')
    expect(formatPercentRange({ low: 0.15, high: 0.15 })).toBe('15%')
  })

  it('formats assumptions in their unit', () => {
    expect(formatAssumption(250, '$/sf')).toBe('$250/sq ft')
    expect(formatAssumption(0.065, 'rate')).toBe('6.5%')
    expect(formatAssumption(0.09, 'rate/yr')).toBe('9%/yr')
    expect(formatAssumption(12, 'months')).toBe('12 months')
    expect(formatAssumption(10400, '$')).toBe('$10,400')
    expect(formatAssumption(1.5, 'ratio')).toBe('1.5 ratio')
    expect(formatAssumptionRange(200, 320, '$/sf')).toBe('$200–$320/sq ft')
    expect(formatAssumptionRange(9, 16, 'months')).toBe('9–16 months')
    expect(formatAssumptionRange(0.15, 0.25, 'share')).toBe('15–25%')
  })
})

describe('formatMonthYear', () => {
  it('reads the date as written', () => {
    expect(formatMonthYear('2026-09-01')).toBe('Sep 2026')
    expect(formatMonthYear('2018-07-27')).toBe('Jul 2018')
  })
})
