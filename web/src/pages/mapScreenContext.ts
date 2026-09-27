import { useOutletContext } from 'react-router'
import type { Filters } from '../models/filters'
import type { MapFeatures } from '../models/map'
import type { SearchResponse } from '../models/search'

/** What the map screen shares with the panel routes over it (results, report). */
export interface MapScreenContext {
  q: string
  filters: Filters | null
  response: SearchResponse | null
  searchStatus: 'loading' | 'error' | 'ready'
  searchError: string | null
  parsing: 'loading' | 'error' | 'done'
  parseError: string | null
  setFilters: (next: Filters) => void
  select: (id: string | null) => void
  selectedId: string | null
  hoveredId: string | null
  setHoveredId: (id: string | null) => void
  transit: boolean
  setTransit: (on: boolean) => void
  retry: () => void
  /** The search part of the URL (q, f), to carry between results and reports. */
  searchQuery: string
  features: MapFeatures | null
}

export function useMapScreen() {
  return useOutletContext<MapScreenContext>()
}
