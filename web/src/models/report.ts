import type { Estimate, Interval } from './estimate'

/** UI bands. The adapter maps the engine's names onto these. */
export type Band = 'fast_track' | 'conditions' | 'high_risk' | 'unknown'
/** UI severities. Anything the adapter doesn't recognize becomes 'unknown', never clear. */
export type Severity = 'deal_risk' | 'caution' | 'minor' | 'unknown'
export type Confidence = 'high' | 'medium' | 'low'
export type OptionLabel = 'by_right' | 'with_relief'

export interface Versions {
  engine: string
  ruleset: string
  schema: string
  /** ISO date of the oldest input, when known */
  dataAsOf: string | null
  /** ISO date of the zoning code text the rules were read from */
  rulesetAsOf: string | null
}

export interface LeadOption {
  label: OptionLabel
  productType: string
  units: number
  /** Empty = by right */
  relief: string[]
}

/** One parcel as lists, the map and the report header show it. */
export interface Parcel {
  /** Canonical 16-character county ID */
  id: string
  /** City block-lot, e.g. 55-A-137 */
  blockLot: string | null
  name: string
  address: string | null
  municipality: string
  neighborhood: string | null
  zoning: string[]
  lotAreaSqft: number
  currentUse: string
  ownerType: string
  assessedLand: number | null
  /** [lon, lat], EPSG:4326 */
  centroid: [number, number]
  /** False = not a development candidate: outline only, no analysis */
  candidate: boolean
  illustrative: boolean
  assemblyId: string | null
  score: number | null
  /** Null when the parcel has no analysis */
  band: Band | null
  topFlag: { title: string; severity: Severity } | null
  maxLandPrice: Estimate | null
  leadOption: LeadOption | null
}

export interface EvidenceRef {
  source: string
  asOf: string | null
  layer: string | null
  codeSection: string | null
  url: string | null
}

export interface Flag {
  id: string
  category: string
  severity: Severity
  title: string
  cost: Interval | null
  months: Interval | null
  evidence: EvidenceRef[]
  confidence: Confidence
  /** How to resolve it */
  resolution: string
  resolvedByStep: number | null
}

export interface ScoreComponent {
  key: string
  label: string
  points: number
  maxPoints: number
  note: string
}

export interface ProgramOption {
  label: OptionLabel
  productType: string
  units: number
  unitSqft: number
  gfaSqft: number
  /** "type (code section)"; empty = by right */
  relief: string[]
  margin: Estimate
  monthsToPermitReady: Estimate
  approvalProbability: Estimate
  maxLandPrice: Estimate
  revenueBasis: string
  entitlementBasis: string[]
}

export interface NextStep {
  order: number
  action: string
  who: string
  cost: Interval
  why: string
  flagIds: string[]
}

export interface Assumption {
  key: string
  label: string
  value: number
  unit: string
  source: string
  /** A default, not a local benchmark: the UI labels it */
  placeholder: boolean
  editable: boolean
  min: number | null
  max: number | null
}

export type CheckStatus = 'pass' | 'needs_approval' | 'rejected' | 'not_applicable'

/** One zoning rule applied to one building type. */
export interface RuleCheck {
  id: string
  label: string
  /** Zoning code section */
  section: string | null
  status: CheckStatus
  /** What the rule requires and what the lot provides, in `unit` (sq ft or ft) */
  required: number | null
  provided: number | null
  unit: string | null
  /** The approval that fixes a failure; "use_variance" or "implausible" when none can */
  relief: string | null
  note: string | null
}

/** One building type the engine tested on the lot. */
export interface ProgramEvaluation {
  productType: string
  units: number
  outcome: 'by_right' | 'needs_approval' | 'rejected'
  checks: RuleCheck[]
  /** Null when the building is ruled out */
  approvalProbability: Estimate | null
  /** One column per building type in the table */
  representative: boolean
  /** Set when this building is one of the report's options */
  chosenAs: OptionLabel | null
}

export interface RuleChecks {
  district: string
  scenario: 'strict' | 'contextual'
  uncoveredDistricts: string[]
  siteChecks: {
    id: string
    label: string
    section: string
    status: 'applies' | 'clear' | 'unknown'
    note: string | null
  }[]
  notChecked: { label: string; section: string; reason: string }[]
  programs: ProgramEvaluation[]
  /** How the approval odds are computed, in words */
  oddsNote: string
}

/** Everything the report panel renders from the engine. Arrays are rendered generically. */
export interface Analysis {
  verdict: {
    band: Band
    score: number | null
    scoreRange: Estimate | null
    /** Written by the engine. The UI never composes sentences with numbers. */
    headline: string
    landRisk: string | null
  }
  scoreComponents: ScoreComponent[]
  metrics: {
    option: OptionLabel
    monthsToPermitReady: Estimate
    approvalProbability: Estimate
    maxLandPrice: Estimate
    landBasis: { value: number; source: string }
    siteCostPremium: Interval & { drivers: string[] }
    landOverMax: Interval | null
    comps: { count: number; radiusMi: number; windowMonths: number }
  } | null
  /** Worst first, as ordered by the engine */
  flags: Flag[]
  cleared: string[]
  options: ProgramOption[]
  /** Free first, then the cheapest deal-killer */
  nextSteps: NextStep[]
  assumptions: Assumption[]
  /** Every zoning rule tested, per building type. Null when zoning is not covered */
  ruleChecks: RuleChecks | null
  /** Contextual = side setbacks from the neighbours' actual setbacks (925.06.C) */
  setbackScenario: 'strict' | 'contextual' | null
  lotDimensionsFt: { width: number; depth: number } | null
  versions: Versions
}

/** Where the report's facts came from. */
export interface Freshness {
  parcelsAsOf: string | null
  /** Layers looked up live for this report; everything else is the stored copy */
  live: string[]
  liveAt: string | null
  /** Live lookups that failed, so the stored copy was used */
  fellBack: string[]
}

export interface SiteReport {
  parcel: Parcel
  /** Null when the parcel is not a candidate */
  analysis: Analysis | null
  /** Null when the facts behind the analysis are not stored */
  freshness: Freshness | null
  /** The building the analysis scores when one was asked for; null = the engine's pick */
  program: Program | null
}

/** A building type to score. `units` null = the largest the zoning rules allow. */
export interface Program {
  productType: string
  units: number | null
}
