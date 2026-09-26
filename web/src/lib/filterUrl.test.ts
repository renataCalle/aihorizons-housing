import { describe, expect, it } from 'vitest'
import { DEFAULT_FILTERS } from '../models/filters'
import { decodeFilters, encodeFilters } from './filterUrl'

describe('filters in the URL', () => {
  it('round-trips, including non-ASCII neighborhood names', () => {
    const filters = {
      ...DEFAULT_FILTERS,
      product: { type: 'townhome' as const, units: 3 },
      areas: ['Hazelwood', 'Spring Hill-City View'],
      maxLandPrice: 25_000,
      sort: 'cheapest' as const,
    }
    const encoded = encodeFilters(filters)
    expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/)
    expect(decodeFilters(encoded)).toEqual(filters)
  })

  it('writes nothing for the defaults', () => {
    expect(encodeFilters(DEFAULT_FILTERS)).toBe('')
  })

  it('ignores broken or unknown input', () => {
    expect(decodeFilters('not base64 !!')).toBeNull()
    expect(decodeFilters(null)).toBeNull()
    const withJunk = btoa(JSON.stringify({ areas: ['Hazelwood'], hacked: true }))
    expect(decodeFilters(withJunk)).toEqual({ ...DEFAULT_FILTERS, areas: ['Hazelwood'] })
  })
})
