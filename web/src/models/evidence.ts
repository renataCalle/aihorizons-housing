import type { Estimate, Interval } from './estimate'
import type { Confidence, NextStep, RuleCheck, Severity, Versions } from './report'

export type CaseOutcome = 'granted' | 'denied' | 'withdrawn' | 'pending' | 'unknown'

export interface Case {
  id: string
  /** Neighborhood or zoning district */
  area: string | null
  request: string | null
  outcome: CaseOutcome
  monthsToDecision: number | null
  sourceUrl: string | null
}

/** Zoning board decisions near the lot. */
export interface Precedent {
  /** unavailable: no decisions yet (real lots); illustrative: the mockups' cases */
  status: 'available' | 'unavailable' | 'illustrative'
  /** Why decisions are unavailable */
  note: string | null
  granted: number | null
  total: number | null
  medianMonths: number | null
  cases: Case[]
  aiExtracted: boolean
}

export interface EvidenceSource {
  source: string
  asOf: string | null
  /** The flag had no date; `asOf` is its data layer's as-of date */
  asOfFromLayer: boolean
  codeSection: string | null
  url: string | null
}

/** One finding (`flag.<id>`) or the approvals option (`option.with_relief`) of a report. */
export interface Evidence {
  id: string
  kind: 'finding' | 'approvals'
  /** The finding's title; null for the approvals option (see `program`) */
  title: string | null
  /** The building the approvals are for */
  program: { productType: string; units: number } | null
  category: string
  severity: Severity | null
  confidence: Confidence | null
  cost: Interval | null
  months: Interval | null
  monthsToPermitReady: Estimate | null
  approvalProbability: Estimate | null
  approvalMonths: Estimate | null
  /** "type (code section)" */
  relief: string[]
  entitlementBasis: string[]
  oddsNote: string | null
  /** The rules the building fails */
  ruleChecks: RuleCheck[]
  sources: EvidenceSource[]
  /** The zoning code online, when a section is cited */
  codeUrl: string | null
  howToResolve: string | null
  resolvedBy: NextStep | null
  precedent: Precedent | null
  illustrative: boolean
  versions: Versions
}
