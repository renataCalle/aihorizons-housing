import { beforeEach, describe, expect, it } from 'vitest'
import { DEFAULT_FILTERS } from '../models/filters'
import { useFilters } from './filters'

describe('filters store', () => {
  beforeEach(() => useFilters.getState().reset())

  it('starts from the defaults', () => {
    expect(useFilters.getState().filters).toEqual(DEFAULT_FILTERS)
  })

  it('patches without dropping other fields, and resets', () => {
    useFilters.getState().patch({ areas: ['Hazelwood'], maxLandPrice: 25_000 })
    useFilters.getState().patch({ sort: 'cheapest' })
    const { filters } = useFilters.getState()
    expect(filters.areas).toEqual(['Hazelwood'])
    expect(filters.maxLandPrice).toBe(25_000)
    expect(filters.sort).toBe('cheapest')

    useFilters.getState().reset()
    expect(useFilters.getState().filters).toEqual(DEFAULT_FILTERS)
  })
})
