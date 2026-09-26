import { MapProvider } from '@vis.gl/react-maplibre'
import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { fetchHealth, fetchMapFeatures, fetchParcelLayer } from '../api'
import { TopBar } from '../components/TopBar'
import { useAsync } from '../lib/useAsync'
import { BlueprintMap, type MapView } from '../map/BlueprintMap'
import { MapControls } from '../map/MapControls'
import { MapReadout } from '../map/MapReadout'

/** Hazelwood, where the mock candidates cluster. */
const INITIAL_VIEW: MapView = { longitude: -79.943, latitude: 40.405, zoom: 17 }

/** The map screen. Search, the results list and the inspector card arrive in M2–M3. */
export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const selectedId = params.get('selected')
  const [view, setView] = useState(INITIAL_VIEW)

  const parcels = useAsync('parcels', fetchParcelLayer)
  const features = useAsync('features', fetchMapFeatures)
  const health = useAsync('health', fetchHealth)

  const parcelData = parcels.status === 'ready' ? parcels.data : null
  const selectedName = parcelData?.features.find((f) => f.properties.id === selectedId)
    ?.properties.name

  function select(id: string | null) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (id) next.set('selected', id)
        else next.delete('selected')
        return next
      },
      { replace: true },
    )
  }

  return (
    <MapProvider>
      <main className="map-page">
        <BlueprintMap
          parcels={parcelData}
          features={features.status === 'ready' ? features.data : null}
          selectedId={selectedId}
          onSelect={select}
          initialView={INITIAL_VIEW}
          onViewChange={setView}
        />
        <TopBar illustrative={health.status === 'ready' && health.data.illustrative} />
        {parcels.status === 'error' && (
          <p className="map-error glass" role="alert">
            Couldn't load parcels: {parcels.error.message}.{' '}
            <a href={window.location.href}>Try again</a>
          </p>
        )}
        <MapControls />
        <MapReadout view={view} />
        <p className="visually-hidden" aria-live="polite">
          {selectedName ? `Selected ${selectedName}` : ''}
        </p>
      </main>
    </MapProvider>
  )
}
