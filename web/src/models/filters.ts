import type { Band } from './report'

export type ProductType = 'single_family' | 'duplex' | 'triplex' | 'townhome' | 'walkup'
export type ApprovalPath = 'by_right' | 'special_exception' | 'variance' | 'rezoning' | 'not_allowed'
export type NearFeature = 'transit_stop' | 'park' | 'school' | 'grocery'
export type OwnerType = 'land_bank' | 'ura' | 'city' | 'private' | 'other_public'
export type Constraint = 'undermined' | 'flood_zone' | 'landslide' | 'combined_sewer' | 'steep_slope'
export type SortKey = 'score_desc' | 'headroom_desc' | 'fastest' | 'cheapest'

/** The one filter state that the chips, the filter editor and AI search all read and write. */
export interface Filters {
  product: { type: ProductType; units: number | null } | null
  areas: string[]
  near: { feature: NearFeature; withinFt: number }[]
  /** Empty means any path. */
  approvalPaths: ApprovalPath[]
  /** Empty means all bands. */
  bands: Band[]
  minScore: number | null
  maxLandPrice: number | null
  minMarginPct: number | null
  maxSiteCostPremium: number | null
  lotMinSqft: number | null
  lotMaxSqft: number | null
  vacantOnly: boolean
  ownerTypes: OwnerType[]
  taxDelinquentOnly: boolean
  /** Percent of the lot at 25%+ slope (0–100). */
  maxSteepSlopePct: number | null
  excludeConstraints: Constraint[]
  includeUnknowns: boolean
  maxMonthsToPermit: number | null
  showAssemblies: boolean
  showNearMisses: boolean
  sort: SortKey
}

export const DEFAULT_FILTERS: Filters = {
  product: null,
  areas: [],
  near: [],
  approvalPaths: [],
  bands: [],
  minScore: null,
  maxLandPrice: null,
  minMarginPct: null,
  maxSiteCostPremium: null,
  lotMinSqft: null,
  lotMaxSqft: null,
  vacantOnly: false,
  ownerTypes: [],
  taxDelinquentOnly: false,
  maxSteepSlopePct: null,
  excludeConstraints: [],
  includeUnknowns: true,
  maxMonthsToPermit: null,
  showAssemblies: false,
  showNearMisses: false,
  sort: 'score_desc',
}
