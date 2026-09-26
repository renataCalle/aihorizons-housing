import type { Estimate } from './estimate'

export type Band = 'fast_track' | 'conditions' | 'high_risk' | 'unknown'
/** Anything the adapter doesn't recognize becomes 'unknown', never clear. */
export type Severity = 'deal_risk' | 'caution' | 'unknown'
export type Confidence = 'high' | 'medium' | 'low'
export type ApprovalPath = 'by_right' | 'special_exception' | 'variance' | 'rezoning' | 'not_allowed'

export interface Versions {
  engine: string
  ruleset: string
  schema: string
  /** ISO date */
  dataAsOf: string
}

export interface Source {
  label: string
  dataset: string
  asOf: string | null
  url: string | null
}

export interface Parcel {
  /** Canonical county parcel ID, dashed. */
  id: string
  /** City block-lot (e.g. 16-E-25), when the API provides it. */
  blockLot: string | null
  name: string
  address: string | null
  neighborhood: string
  zoningDistrict: string
  lotAreaSqft: number
  currentUse: string
  ownerType: string
  assessedValue: number | null
  listedPrice: number | null
  /** [lon, lat], EPSG:4326 */
  centroid: [number, number]
  score: number | null
  band: Band
}

export interface ProgramOption {
  product: string
  units: number
  sqftEach: number | null
  tenure: string
  margin: Estimate
  monthsToPermitReady: Estimate
  approvalPath: ApprovalPath
  relief: string[]
  codeBasis: string | null
  precedent: { granted: number; total: number } | null
  evidenceId: string | null
}

export interface ScoreComponent {
  key: string
  label: string
  points: number
  maxPoints: number
  note: string
}

export interface Finding {
  id: string
  severity: Severity
  title: string
  detail: string
  impactCost: Estimate | null
  impactMonths: Estimate | null
  impactLabel: string
  sources: Source[]
  confidence: Confidence
  confidenceNote: string | null
  resolvedByStep: number | null
  evidenceId: string | null
}

export interface NextStep {
  order: number
  title: string
  why: string
  who: string
  cost: Estimate
  durationLabel: string
}

export interface Assumption {
  key: string
  label: string
  value: Estimate | number | string
  sourceLabel: string
  editable: boolean
}

/** Everything the report panel renders. Arrays are rendered generically. */
export interface SiteReport {
  parcel: Parcel
  verdict: {
    band: Band
    score: number | null
    scoreRange: Estimate | null
    /** Written by the API. The UI never composes sentences with numbers. */
    headline: string
  }
  scoreComponents: ScoreComponent[]
  headline: {
    approvalPath: ApprovalPath
    approvalProbability: Estimate | null
    approvalSummary: string
    monthsToPermitReady: Estimate
    siteCostPremium: Estimate
    siteCostSummary: string
    maxLandPrice: Estimate
    targetMarginPct: number
    listedPrice: number | null
    comps: { count: number; radiusMi: number; windowMonths: number }
  }
  /** Worst first, as ordered by the engine. */
  findings: Finding[]
  cleared: { label: string; source: Source | null }[]
  bestByRight: ProgramOption | null
  bestWithApprovals: ProgramOption | null
  nextSteps: NextStep[]
  assumptions: Assumption[]
  versions: Versions
  illustrative: boolean
}
