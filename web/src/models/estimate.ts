export type Unit = 'usd' | 'usd_per_sqft' | 'pct' | 'months' | 'sqft' | 'points'

/** Every estimate is a range. The UI shows p10–p90; p50 is a marker when the API sends it. */
export interface Estimate {
  p10: number
  p50: number | null
  p90: number
  unit: Unit
}
