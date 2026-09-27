import type { DetectedKind, IdFormat } from '../search/detect'
import type { Filters } from './filters'
import type { Estimate } from './estimate'
import type { Band, Parcel } from './report'

export interface LookupMatch {
  matchedOn: 'county_id' | 'block_lot' | 'address'
  parcel: Parcel
}

export interface LookupResult {
  kind: DetectedKind
  format: IdFormat | null
  matches: LookupMatch[]
}

/** One active filter. `key` says what removing it resets (see removeChip in the adapter). */
export interface FilterChip {
  key: string
  label: string
}

/** A building type the engine tested on the lot. */
export interface ProgramFit {
  productType: string
  units: number
  outcome: 'by_right' | 'needs_approval' | 'rejected'
  reliefTypes: string[]
}

/**
 * What a lot is scored on in a search: the searched building type, or the engine's pick.
 * `basis`: 'pick' = the engine's pick; 'exact' = the unit count searched; 'up_to' = the
 * largest unit count the zoning rules allow for the searched type.
 */
export interface ScoredProgram {
  /** Null = no building the engine tested fits */
  productType: string | null
  units: number | null
  basis: 'pick' | 'exact' | 'up_to'
  score: number | null
  band: Band | null
  outcome: 'by_right' | 'needs_approval' | 'rejected' | 'not_covered' | null
  reliefTypes: string[]
  monthsToPermit: Estimate | null
  maxLandPrice: Estimate | null
}

export interface SearchResult {
  rank: number
  parcel: Parcel
  /** The program that matched the product filter; null without one. */
  fit: ProgramFit | null
  /** What the lot is ranked on */
  scored: ScoredProgram | null
  /** The engine's pick, when a building type was searched and the pick is another type */
  betterFit: ScoredProgram | null
}

export interface SearchResponse {
  total: number
  filters: Filters
  /** The building type lots are ranked for; null = best fit (the engine's pick) */
  rankedFor: { type: string; units: number | null } | null
  chips: FilterChip[]
  results: SearchResult[]
  /** Candidates that fail exactly one filter, and which. */
  nearMisses: { parcel: Parcel; failed: FilterChip }[]
  assemblies: { id: string; parcelIds: string[] }[]
  /** Filters the data can't answer yet; the search ignored them. */
  notApplied: FilterChip[]
  /** When nothing matches: the chip whose removal brings back the most sites. */
  suggestion: { remove: FilterChip; wouldReturn: number } | null
}

export interface ParseResult {
  filters: Filters
  chips: FilterChip[]
  readings: { phrase: string; interpretedAs: string }[]
  notUnderstood: string[]
  detected: 'parcel_id' | 'address' | 'description'
  /** 'rules' = basic search, AI unavailable */
  parser: 'ai' | 'rules'
}

/** Example searches for the landing page, from the data being served. */
export interface Examples {
  parcelId: string
  address: string
  prompt: string
}

export interface Neighborhood {
  name: string
  candidates: number
}
