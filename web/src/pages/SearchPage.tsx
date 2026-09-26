import { MapProvider } from '@vis.gl/react-maplibre'
import { useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import {
  fetchHealth,
  fetchMapFeatures,
  fetchParcelLayer,
  fetchParse,
  fetchSearch,
  fetchSiteReport,
} from '../api'
import { removeChip } from '../api/adapters'
import { TopBar } from '../components/TopBar'
import { decodeFilters, encodeFilters } from '../lib/filterUrl'
import { useAsync } from '../lib/useAsync'
import { DEFAULT_FILTERS, type Filters } from '../models/filters'
import type { ParcelLayer } from '../models/map'
import type { SearchResponse } from '../models/search'
import { BlueprintMap, type MapView } from '../map/BlueprintMap'
import { MapControls } from '../map/MapControls'
import { MapReadout } from '../map/MapReadout'
import { AreaOverlay, FitToAreas, LeaderLine, RankTags } from '../map/SearchOverlays'
import { InspectorCard } from '../results/InspectorCard'
import { LayersMenu } from '../results/LayersMenu'
import { ResultsPanel } from '../results/ResultsPanel'

/** Hazelwood, where the mock candidates cluster. */
const INITIAL_VIEW: MapView = { longitude: -79.943, latitude: 40.405, zoom: 16.4 }

/** Color only the matches; every other parcel is drawn as an outline (docs/01, §3). */
function matchLayer(parcels: ParcelLayer, response: SearchResponse | null): ParcelLayer {
  if (!response) return parcels
  const ranks = new Map(response.results.map((r) => [r.parcel.id, r.rank]))
  const showAssemblies = response.filters.showAssemblies
  return {
    ...parcels,
    features: parcels.features.map((f) => {
      const rank = ranks.get(f.properties.id)
      return {
        ...f,
        properties: {
          ...f.properties,
          band: rank ? f.properties.band : 'none',
          rank: rank ?? null,
          assemblyId: showAssemblies ? f.properties.assemblyId : null,
        },
      }
    }),
  }
}

/** The results screen (docs/01, §3). The URL holds the query, the filters and the selection. */
export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const selectedId = params.get('selected')
  const fromUrl = useMemo(() => decodeFilters(params.get('f')), [params])
  const [view, setView] = useState(INITIAL_VIEW)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [transit, setTransit] = useState(true)
  const [retry, setRetry] = useState(0)
  const cardRef = useRef<HTMLElement>(null)

  // Text without filters in the URL is parsed first; then the filters live in the URL.
  const parse = useAsync(fromUrl || !q ? 'none' : `parse:${q}`, (signal) =>
    fromUrl || !q ? Promise.resolve(null) : fetchParse(q, null, signal),
  )
  const parsed = parse.status === 'ready' ? parse.data : null
  const filters: Filters | null = fromUrl ?? (q ? (parsed?.filters ?? null) : DEFAULT_FILTERS)

  const searchKey = filters ? `${encodeFilters(filters)}#${retry}` : 'waiting'
  const search = useAsync(searchKey, (signal) =>
    filters ? fetchSearch(filters, signal) : new Promise<never>(() => {}),
  )
  const response = search.status === 'ready' ? search.data : search.stale

  const parcels = useAsync('parcels', fetchParcelLayer)
  const features = useAsync('features', fetchMapFeatures)
  const health = useAsync('health', fetchHealth)

  const layer = useMemo(
    () => (parcels.status === 'ready' ? matchLayer(parcels.data, response) : null),
    [parcels, response],
  )

  const selectedResult =
    response?.results.find((r) => r.parcel.id === selectedId) ??
    response?.nearMisses.find((n) => n.parcel.id === selectedId)
  const fetched = useAsync(selectedId && !selectedResult ? `sel:${selectedId}` : 'none', (signal) =>
    selectedId && !selectedResult ? fetchSiteReport(selectedId, signal) : Promise.resolve(null),
  )
  const selectedParcel =
    selectedResult?.parcel ?? (fetched.status === 'ready' ? fetched.data?.parcel : null) ?? null
  const selectedRank = response?.results.find((r) => r.parcel.id === selectedId)?.rank ?? null
  const selectedFit = response?.results.find((r) => r.parcel.id === selectedId)?.fit ?? null

  function update(patch: Record<string, string | null>) {
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
    )
  }

  const setFilters = (next: Filters) => update({ f: encodeFilters(next) || null })
  const select = (id: string | null) => update({ selected: id })

  return (
    <MapProvider>
      <main className="map-page">
        <BlueprintMap
          parcels={layer}
          features={features.status === 'ready' ? features.data : null}
          selectedId={selectedId}
          onSelect={select}
          initialView={INITIAL_VIEW}
          onViewChange={setView}
          hoveredId={hoveredId}
          onHover={setHoveredId}
          showTransit={transit}
        >
          {features.status === 'ready' && filters && (
            <>
              <AreaOverlay features={features.data} areas={filters.areas} />
              <FitToAreas features={features.data} areas={filters.areas} />
            </>
          )}
          {response && <RankTags results={response.results} />}
        </BlueprintMap>

        <TopBar
          illustrative={health.status === 'ready' && health.data.illustrative}
          query={q}
          basicSearch={parsed?.parser === 'rules'}
        />

        {filters && (
          <ResultsPanel
            response={response}
            loading={search.status === 'loading'}
            error={search.status === 'error' ? search.error.message : null}
            filters={filters}
            onFilters={setFilters}
            onRemoveChip={(key) => setFilters(removeChip(filters, key))}
            selectedId={selectedId}
            hoveredId={hoveredId}
            onSelect={select}
            onHover={setHoveredId}
            onRetry={() => setRetry((n) => n + 1)}
            layers={<LayersMenu transit={transit} onTransit={setTransit} />}
          />
        )}
        {q && !filters && (
          <p className="results-panel glass label" role="status">
            {parse.status === 'error' ? `Couldn't read that search: ${parse.error.message}` : 'Reading your search…'}
          </p>
        )}

        {selectedParcel && (
          <>
            <InspectorCard
              ref={cardRef}
              parcel={selectedParcel}
              fit={selectedFit}
              rank={selectedRank}
              total={response?.total ?? 0}
              onClose={() => select(null)}
            />
            <LeaderLine at={selectedParcel.centroid} cardRef={cardRef} />
          </>
        )}

        <MapControls />
        <MapReadout view={view} />
      </main>
    </MapProvider>
  )
}
