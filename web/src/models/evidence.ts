import type { Confidence } from './report'

export type CaseOutcome = 'granted' | 'denied' | 'withdrawn' | 'pending'

export interface Evidence {
  id: string
  kind: string
  title: string
  appliesTo: string
  code: { section: string; asOf: string; summary: string; url: string | null } | null
  precedent: { granted: number; total: number } | null
  medianMonths: number | null
  cases: {
    id: string
    neighborhood: string
    request: string
    outcome: CaseOutcome
    monthsToDecision: number | null
    sourceUrl: string | null
  }[]
  aiExtracted: boolean
  confidence: Confidence
  confidenceNote: string
  howToResolve: string
}
