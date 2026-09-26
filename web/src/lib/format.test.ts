import { describe, expect, it } from 'vitest'
import { formatMoneyRange, formatMonthsRange, formatNumberRange, formatSqft } from './format'

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
})
