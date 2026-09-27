import type { DetectedKind, IdFormat } from '../search/detect'
import type { Filters } from './filters'
import type { Parcel } from './report'

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

export interface SearchResult {
  rank: number
  parcel: Parcel
  /** The program that matched the product filter; null without one. */
  fit: ProgramFit | null
}

export interface SearchResponse {
  total: number
  filters: Filters
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
