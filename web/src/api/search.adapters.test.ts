import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { DEFAULT_FILTERS, type Filters } from '../models/filters'
import { removeChip, toApiFilters, toFilters, toParseResult } from './adapters'

const sample = JSON.parse(
  readFileSync(
    new URL('../../../fixtures/mock/ui-draft/sample.parse_result.json', import.meta.url),
    'utf8',
  ),
)

const FILTERS: Filters = {
  ...DEFAULT_FILTERS,
  product: { type: 'townhome', units: 3 },
  areas: ['Hazelwood', 'Greenfield'],
  near: [{ feature: 'transit_stop', withinFt: 1320 }],
  approvalPaths: ['by_right'],
  bands: ['conditions', 'unknown'],
  maxLandPrice: 25_000,
  lotMinSqft: 3_000,
  lotMaxSqft: 6_000,
  excludeConstraints: ['undermined', 'flood_zone'],
}

describe('filters to and from the API', () => {
  it('round-trips, mapping bands to the engine names', () => {
    const api = toApiFilters(FILTERS)
    expect(api.bands).toEqual(['feasible_with_conditions', 'not_scored'])
    expect(api.near).toEqual([{ feature: 'transit_stop', within_ft: 1320 }])
    expect(toFilters(api)).toEqual(FILTERS)
  })

  it('reads the sample parse result', () => {
    const parsed = toParseResult({ ...sample, chips: [], parser: 'rules' })
    expect(parsed.filters.product).toEqual({ type: 'townhome', units: 3 })
    expect(parsed.filters.maxLandPrice).toBe(25_000)
    expect(parsed.readings[0].interpretedAs).toBeTruthy()
  })
})

describe('removeChip', () => {
  it('removes one area, one constraint or one near filter', () => {
    expect(removeChip(FILTERS, 'area:Hazelwood').areas).toEqual(['Greenfield'])
    expect(removeChip(FILTERS, 'constraint:undermined').excludeConstraints).toEqual(['flood_zone'])
    expect(removeChip(FILTERS, 'near:transit_stop').near).toEqual([])
  })

  it('resets both lot bounds and plain fields to their defaults', () => {
    const noLot = removeChip(FILTERS, 'lot_size')
    expect([noLot.lotMinSqft, noLot.lotMaxSqft]).toEqual([null, null])
    expect(removeChip(FILTERS, 'approval_paths').approvalPaths).toEqual([])
    expect(removeChip(FILTERS, 'product').product).toBeNull()
  })

  it('leaves everything else alone', () => {
    const { maxLandPrice, ...rest } = removeChip(FILTERS, 'max_land_price')
    const { maxLandPrice: _, ...before } = FILTERS
    expect(maxLandPrice).toBeNull()
    expect(rest).toEqual(before)
  })
})
