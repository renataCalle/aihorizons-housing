import { MapProvider } from '@vis.gl/react-maplibre'
import { useCallback, useMemo, useState } from 'react'
import { Outlet, useMatch, useNavigate, useSearchParams } from 'react-router'
import { fetchHealth, fetchMapFeatures, fetchParcelLayer, fetchParse, fetchSearch } from '../api'
import { TopBar } from '../components/TopBar'
import { decodeFilters, encodeFilters, filterParam } from '../lib/filterUrl'
import { useAsync } from '../lib/useAsync'
import { DEFAULT_FILTERS, type Filters } from '../models/filters'
import type { ParcelLayer } from '../models/map'
import type { SearchResponse } from '../models/search'
import { BlueprintMap, type MapView } from '../map/BlueprintMap'
import { MapControls } from '../map/MapControls'
import { MapReadout } from '../map/MapReadout'
import type { MapScreenContext } from './mapScreenContext'
import { ringCenter } from '../map/readout'
import {
  AreaOverlay,
  FitToAreas,
  FlyToSelection,
  RankTags,
  type Padding,
} from '../map/SearchOverlays'

/** Hazelwood, where the mock candidates cluster. */
const INITIAL_VIEW: MapView = { longitude: -79.943, latitude: 40.405, zoom: 16.4 }

/** Room the panels take on each side, so the selected parcel stays in view. */
const RESULTS_PADDING: Padding = { top: 110, bottom: 90, left: 420, right: 360 }
const REPORT_PADDING: Padding = { top: 180, bottom: 90, left: 40, right: 760 }

/** Color only the matches; every other parcel is drawn as an outline (docs/01, §3). */
function matchLayer(parcels: ParcelLayer, response: SearchResponse | null): ParcelLayer {
  if (!response) return parcels
  const ranks = new Map(response.results.map((r) => [r.parcel.id, r.rank]))
  // Colour by what each lot is ranked on: the searched building type, or the engine's pick.
  const bands = new Map(response.results.map((r) => [r.parcel.id, r.scored?.band]))
  const scores = new Map(response.results.map((r) => [r.parcel.id, r.scored?.score]))
  const showAssemblies = response.filters.showAssemblies
  return {
    ...parcels,
    features: parcels.features.map((f) => {
      const rank = ranks.get(f.properties.id)
      return {
        ...f,
        properties: {
          ...f.properties,
          band: rank ? (bands.get(f.properties.id) ?? f.properties.band) : 'none',
          // The 3D view raises each lot by the same score it is coloured by.
          score: rank ? (scores.get(f.properties.id) ?? f.properties.score) : null,
          rank: rank ?? null,
          assemblyId: showAssemblies ? f.properties.assemblyId : null,
        },
      }
    }),
  }
}

/**
 * The map screen: one map that stays mounted while panels change over it (results at
 * /search, the report at /parcel/:id, the evidence drawer over the report). The URL holds
 * the query (q), the filters (f) and, on /search, the selection.
 */
export function MapScreen() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const report = useMatch('/parcel/:id/*')
  const reportId = report?.params.id ?? null
  const q = params.get('q') ?? ''
  const fromUrl = useMemo(() => decodeFilters(params.get('f')), [params])
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  // Transit stops: a manual choice from the Layers menu, until the search changes (below).
  const [transitChoice, setTransitChoice] = useState<{ auto: boolean; on: boolean } | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  // Text without filters in the URL is parsed first; then the filters live in the URL.
  const parse = useAsync(fromUrl || !q ? 'none' : `parse:${q}`, (signal) =>
    fromUrl || !q ? Promise.resolve(null) : fetchParse(q, null, signal),
  )
  const parsed = parse.status === 'ready' ? parse.data : null
  const filters: Filters | null = fromUrl ?? (q ? (parsed?.filters ?? null) : DEFAULT_FILTERS)

  // Stops show only when the search is about transit ("near a bus stop"). A manual toggle
  // holds until a search turns that condition on or off.
  const transitAuto = !!filters?.near.some((n) => n.feature === 'transit_stop')
  const transit =
    transitChoice && transitChoice.auto === transitAuto ? transitChoice.on : transitAuto
  const setTransit = useCallback(
    (on: boolean) => setTransitChoice({ auto: transitAuto, on }),
    [transitAuto],
  )

  const search = useAsync(filters ? `${encodeFilters(filters)}#${retryCount}` : 'waiting', (s) =>
    filters ? fetchSearch(filters, s) : new Promise<never>(() => {}),
  )
  const response = search.status === 'ready' ? search.data : search.stale

  const parcels = useAsync('parcels', fetchParcelLayer)
  const features = useAsync('features', fetchMapFeatures)
  const health = useAsync('health', fetchHealth)
  const featureData = features.status === 'ready' ? features.data : null

  const layer = useMemo(
    () => (parcels.status === 'ready' ? matchLayer(parcels.data, response) : null),
    [parcels, response],
  )

  const selectedId = reportId ?? params.get('selected')
  // 3D score view (docs/01, "3D score view"): lots raised by score, camera tilted.
  const view3d = params.get('view') === '3d'
  const selectedCenter = useMemo(() => {
    if (!selectedId) return null
    const hit =
      response?.results.find((r) => r.parcel.id === selectedId) ??
      response?.nearMisses.find((n) => n.parcel.id === selectedId)
    if (hit) return hit.parcel.centroid
    // Not among the results (e.g. opened from the search box): use its shape on the map.
    const feature =
      parcels.status === 'ready'
        ? parcels.data.features.find((f) => f.properties.id === selectedId)
        : undefined
    return feature ? ringCenter(feature.geometry) : null
  }, [response, selectedId, parcels])

  const searchParams = new URLSearchParams()
  if (q) searchParams.set('q', q)
  const f = filters ? filterParam(filters, !!q) : null
  if (f) searchParams.set('f', f)
  const searchQuery = searchParams.toString()

  // Stable callbacks: the results list is memoized and only re-renders rows that change.
  const update = useCallback(
    (patch: Record<string, string | null>) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [key, value] of Object.entries(patch)) {
            if (value) next.set(key, value)
            else next.delete(key)
          }
          return next
        },
        { replace: true },
      ),
    [setParams],
  )
  const select = useCallback((id: string | null) => update({ selected: id }), [update])
  const setFilters = useCallback(
    (next: Filters) => update({ f: filterParam(next, !!q) }),
    [update, q],
  )

  const context: MapScreenContext = {
    q,
    filters,
    response,
    searchStatus: search.status,
    searchError: search.status === 'error' ? search.error.message : null,
    parsing: parse.status === 'loading' ? 'loading' : parse.status === 'error' ? 'error' : 'done',
    parseError: parse.status === 'error' ? parse.error.message : null,
    setFilters,
    select,
    selectedId,
    hoveredId,
    setHoveredId,
    transit,
    setTransit,
    retry: () => setRetryCount((n) => n + 1),
    searchQuery,
    features: featureData,
  }

  // With a report open, clicking another parcel opens its report; otherwise it selects it.
  const onMapSelect = (id: string | null) => {
    if (!reportId) return context.select(id)
    if (id && id !== reportId) navigate(`/parcel/${id}${searchQuery ? `?${searchQuery}` : ''}`)
  }

  return (
    <MapProvider>
      <main className={reportId ? 'map-page has-report' : 'map-page'}>
        <BlueprintMap
          parcels={layer}
          features={featureData}
          selectedId={selectedId}
          onSelect={onMapSelect}
          initialView={INITIAL_VIEW}
          hoveredId={hoveredId}
          onHover={setHoveredId}
          showTransit={transit}
          view3d={view3d}
        >
          {featureData && filters && (
            <>
              <AreaOverlay features={featureData} areas={filters.areas} />
              {!selectedId && <FitToAreas features={featureData} areas={filters.areas} />}
            </>
          )}
          {response && <RankTags results={response.results} />}
          <FlyToSelection
            center={selectedCenter}
            padding={reportId ? REPORT_PADDING : RESULTS_PADDING}
          />
        </BlueprintMap>

        <TopBar
          illustrative={health.status === 'ready' && health.data.illustrative}
          query={q}
          basicSearch={parsed?.parser === 'rules'}
        />

        <Outlet context={context} />

        <MapControls
          view3d={view3d}
          onToggle3d={() => update({ view: view3d ? null : '3d' })}
        />
        <MapReadout initial={INITIAL_VIEW} />
      </main>
    </MapProvider>
  )
}
