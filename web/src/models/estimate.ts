/** Every engine estimate is a range. The UI shows p10–p90 and can mark p50. */
export interface Estimate {
  p10: number
  p50: number
  p90: number
}

/** A plain low–high span (costs, months). `{ low: 0, high: 0 }` means free or none. */
export interface Interval {
  low: number
  high: number
}

export function spanOf(estimate: Estimate): Interval {
  return { low: estimate.p10, high: estimate.p90 }
}
