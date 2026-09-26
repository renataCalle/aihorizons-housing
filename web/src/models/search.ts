import type { DetectedKind, IdFormat } from '../search/detect'
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
