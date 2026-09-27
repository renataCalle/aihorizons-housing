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
  /** The search part of the URL (q, f). Empty when the page wasn't opened from a search. */
  searchQuery: string
  /** What links between results and reports carry: the search plus the view (view=3d, panel=area). */
  linkQuery: string
  features: MapFeatures | null
  /** The 3D view is on */
  view3d: boolean
  /** The left panel shows the area view (the searched lots at a glance) instead of the list */
  areaView: boolean
  /** Switch the panel view, optionally changing the filters in the same URL update */
  setAreaView: (on: boolean, filters?: Filters) => void
}

export function useMapScreen() {
  return useOutletContext<MapScreenContext>()
}
