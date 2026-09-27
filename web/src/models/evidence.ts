import type { Estimate, Interval } from './estimate'
import type { Confidence, NextStep, RuleCheck, Severity, Versions } from './report'

export type CaseOutcome = 'granted' | 'denied' | 'withdrawn' | 'pending' | 'unknown'

export interface Case {
  id: string
  /** Neighborhood or zoning district */
  area: string | null
  /** What was asked, in words (mock cases) */
  request: string | null
  /** Approval types asked for, e.g. variance (real cases) */
  reliefTypes: string[]
  /** ISO date of the decision */
  decided: string | null
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
  /** What the engine counts as a similar case, in words */
  rule: string | null
  /** Where the decisions come from */
  source: string | null
  /** ISO date of the latest decision in the data */
  asOf: string | null
  /** Decided cases near the lot, similar or not */
  nearby: number | null
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

/** A zoning code section, explained. */
export interface CodeSection {
  section: string
  title: string | null
  /** One plain-language sentence, drafted from the code text */
  summary: string | null
  url: string | null
  /** ISO date of the code text the summary was read from */
  asOf: string | null
  /** ISO date of the section's latest amendment, when known */
  effective: string | null
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
  /** The code sections this evidence cites, explained */
  codeSections: CodeSection[]
  howToResolve: string | null
  resolvedBy: NextStep | null
  precedent: Precedent | null
  illustrative: boolean
  versions: Versions
}
