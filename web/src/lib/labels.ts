import type { SortKey } from '../models/filters'
import type { Band } from '../models/report'

/** Short band names for pills, list rows and legends. Sentence case (docs/01, copy rules). */
export const BAND_LABEL: Record<Band, string> = {
  fast_track: 'Fast track',
  // Not bare "Conditions": next to a score, "61 Conditions" reads as a count.
  conditions: 'With conditions',
  high_risk: 'High risk',
  unknown: 'Not scored',
}

export const SORT_LABEL: Record<SortKey, { menu: string; heading: string }> = {
  score_desc: { menu: 'score', heading: 'best first' },
  cheapest: { menu: 'land price', heading: 'cheapest first' },
  fastest: { menu: 'time to permit', heading: 'fastest first' },
  headroom_desc: { menu: 'land headroom', heading: 'most headroom first' },
}

const RELIEF_LABEL: Record<string, string> = {
  subdivision: 'Subdivision',
  administrator_exception: 'Administrator exception',
  special_exception: 'Special exception',
  variance: 'Variance',
  use_variance: 'Use variance',
  conditional_use: 'Conditional use',
  rezoning: 'Rezoning',
}

/** Short approval names for table chips. */
export function reliefShortLabel(type: string): string {
  if (type === 'administrator_exception') return 'Admin. exception'
  return RELIEF_LABEL[type] ?? type.replace(/_/g, ' ')
}

/** "3 townhomes", "Duplex", "6-unit walk-up"; without a unit count: "Townhomes", "Walk-up". */
export function programLabel(productType: string, units: number | null): string {
  switch (productType) {
    case 'townhome':
      return units === null ? 'Townhomes' : `${units} townhome${units === 1 ? '' : 's'}`
    case 'walkup':
      return units === null ? 'Walk-up' : `${units}-unit walk-up`
    case 'single_family':
      return 'Single-family home'
    default:
      return productType.charAt(0).toUpperCase() + productType.slice(1).replace('_', ' ')
  }
}

/**
 * "By-right", or the approvals needed: "Subdivision + Variance". The same approval for two
 * rules reads "Administrator exception ×2".
 */
export function approvalLabel(reliefTypes: string[]): string {
  const counts = new Map<string, number>()
  for (const r of reliefTypes) if (r in RELIEF_LABEL) counts.set(r, (counts.get(r) ?? 0) + 1)
  if (!counts.size) return 'By-right'
  return [...counts]
    .map(([r, n]) => (n > 1 ? `${RELIEF_LABEL[r]} ×${n}` : RELIEF_LABEL[r]))
    .join(' + ')
}

/** Relief strings from the engine look like "variance (903.03)". */
export function reliefType(relief: string): string {
  return relief.split(' (')[0].trim().toLowerCase().replace(/ /g, '_')
}

const PRODUCT_NOUN: Record<string, [singular: string, plural: string]> = {
  single_family: ['Single-family', 'single-family homes'],
  duplex: ['Duplex', 'duplexes'],
  triplex: ['Triplex', 'triplexes'],
  townhome: ['Townhome', 'townhomes'],
  walkup: ['Walk-up', 'walk-ups'],
}

/** List header: "ranked for townhomes", "ranked for 3 townhomes". */
export function rankedForLabel(productType: string, units: number | null): string {
  return units === null
    ? (PRODUCT_NOUN[productType]?.[1] ?? productType)
    : programLabel(productType, units).toLowerCase()
}

/** Legend title in a building-type search: "Townhome feasibility". */
export function feasibilityLabel(productType: string): string {
  return `${PRODUCT_NOUN[productType]?.[0] ?? productType} feasibility`
}

/** Types whose unit count is fixed: "up to" only makes sense for townhomes and walk-ups. */
const FIXED_UNITS = new Set(['single_family', 'duplex', 'triplex'])

/**
 * The building a score is for: "Single-family home", "2 townhomes", or "Up to 2 townhomes"
 * when the lot was scored at the most the rules allow rather than the count searched.
 */
export function scoredLabel(p: {
  productType: string | null
  units: number | null
  basis: 'pick' | 'exact' | 'up_to'
}): string {
  if (!p.productType) return 'No building fits'
  const label = programLabel(p.productType, p.units)
  return p.basis === 'up_to' && !FIXED_UNITS.has(p.productType) && p.units !== null
    ? `Up to ${label.toLowerCase()}`
    : label
}
