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

/**
 * Max land price at the target margin. The engine returns negative values when building costs
 * exceed the finished value: then no land price works.
 */
export function formatMaxLand({ low, high }: Interval): string {
  if (high <= 0) return 'None at target margin'
  if (low < 0) return `Up to ${formatMoneyRange({ low: high, high })}`
  return formatMoneyRange({ low, high })
}

/** 0.15 -> "15%", -0.52 -> "-52%" */
export function formatPercent(share: number): string {
  return `${Math.round(share * 100)}%`
}

/** "-52% to -32%": "to" rather than a dash, which reads as a minus next to negatives. */
export function formatPercentRange({ low, high }: Interval): string {
  const lo = formatPercent(low)
  const hi = formatPercent(high)
  return lo === hi ? lo : `${lo} to ${hi}`
}

/** "$1,500" (not abbreviated) */
export function formatDollars(value: number): string {
  return `${value < 0 ? '-' : ''}$${Math.round(Math.abs(value)).toLocaleString('en-US')}`
}

function assumptionParts(value: number, unit: string): [string, string, string] {
  switch (unit) {
    case '$/sf':
      return ['$', String(Math.round(value)), '/sq ft']
    case 'share':
    case 'rate':
      return ['', String(+(value * 100).toFixed(1)), '%']
    case 'rate/yr':
      return ['', String(+(value * 100).toFixed(1)), '%/yr']
    case 'months':
      return ['', String(value), ' months']
    default:
      return ['', String(value), ` ${unit}`]
  }
}

/** An engine assumption in its unit: "$250/sq ft", "20%", "9%/yr", "12 months". */
export function formatAssumption(value: number, unit: string): string {
  return assumptionParts(value, unit).join('')
}

/** An assumption's range, unit once: "$200–$320/sq ft", "15–25%", "9–16 months". */
export function formatAssumptionRange(min: number, max: number, unit: string): string {
  const [pre, lo, post] = assumptionParts(min, unit)
  const hi = assumptionParts(max, unit)[1]
  return lo === hi ? `${pre}${lo}${post}` : `${pre}${lo}${EN_DASH}${pre}${hi}${post}`
}

/** "VACANT LAND" -> "Vacant land" */
export function sentenceCase(text: string): string {
  const lower = text.toLowerCase()
  return lower.charAt(0).toUpperCase() + lower.slice(1)
}
