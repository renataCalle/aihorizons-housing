import type { Estimate } from '../models/estimate'

const EN_DASH = '–'

function money(value: number): string {
  if (value === 0) return 'Free'
  const abs = Math.abs(value)
  if (abs >= 1_000_000) return `$${+(value / 1_000_000).toFixed(1)}M`
  if (abs >= 1_000) return `$${Math.round(value / 1_000)}k`
  return `$${Math.round(value)}`
}

/** p10–p90 as a compact range: "$24k–$41k", "5–7 months", "66–78". */
export function formatRange(estimate: Estimate): string {
  const { p10, p90, unit } = estimate
  switch (unit) {
    case 'usd':
      return p10 === 0 && p90 === 0 ? 'Free' : `${money(p10)}${EN_DASH}${money(p90)}`
    case 'months':
      return p10 === p90 ? `${p10} months` : `${p10}${EN_DASH}${p90} months`
    case 'pct':
      return `${p10}${EN_DASH}${p90}%`
    default:
      return `${p10}${EN_DASH}${p90}`
  }
}
