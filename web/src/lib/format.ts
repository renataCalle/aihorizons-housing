import type { Interval } from '../models/estimate'

const EN_DASH = '–'

function money(value: number): string {
  const sign = value < 0 ? '-' : ''
  const abs = Math.abs(value)
  if (abs >= 1_000_000) return `${sign}$${+(abs / 1_000_000).toFixed(1)}M`
  if (abs >= 1_000) return `${sign}$${Math.round(abs / 1_000)}k`
  return `${sign}$${Math.round(abs)}`
}

/** "$24k–$41k"; "Free" for a no-cost span. */
export function formatMoneyRange({ low, high }: Interval): string {
  if (low === 0 && high === 0) return 'Free'
  return low === high ? money(low) : `${money(low)}${EN_DASH}${money(high)}`
}

/** "5–7 months" */
export function formatMonthsRange({ low, high }: Interval): string {
  const lo = Math.round(low)
  const hi = Math.round(high)
  return lo === hi ? `${lo} months` : `${lo}${EN_DASH}${hi} months`
}

/** "66–78" */
export function formatNumberRange({ low, high }: Interval): string {
  return `${Math.round(low)}${EN_DASH}${Math.round(high)}`
}

/** "3,960 sq ft" */
export function formatSqft(value: number): string {
  return `${Math.round(value).toLocaleString('en-US')} sq ft`
}
