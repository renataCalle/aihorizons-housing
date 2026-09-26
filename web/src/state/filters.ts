import { create } from 'zustand'
import { DEFAULT_FILTERS, type Filters } from '../models/filters'

interface FiltersState {
  filters: Filters
  /** Merge a partial update, e.g. from a chip, the filter editor or an AI search parse. */
  patch: (update: Partial<Filters>) => void
  replace: (filters: Filters) => void
  reset: () => void
}

export const useFilters = create<FiltersState>()((set) => ({
  filters: DEFAULT_FILTERS,
  patch: (update) => set((state) => ({ filters: { ...state.filters, ...update } })),
  replace: (filters) => set({ filters }),
  reset: () => set({ filters: DEFAULT_FILTERS }),
}))
