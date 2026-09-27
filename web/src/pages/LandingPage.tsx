import { MapProvider } from '@vis.gl/react-maplibre'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { fetchExamples, fetchHealth, fetchMapFeatures, fetchParcelLayer } from '../api'
import { BrandMark } from '../components/BrandMark'
import { useAsync } from '../lib/useAsync'
import { BlueprintMap, type MapView } from '../map/BlueprintMap'
import { MapControls } from '../map/MapControls'
import { Omnibox } from '../search/Omnibox'
import { useMapTheme } from '../state/mapTheme'

/** Hazelwood, Greenfield and Glen Hazel, where the mock lots are. */
const LANDING_VIEW: MapView = { longitude: -79.936, latitude: 40.4115, zoom: 14.9 }


/** Landing (docs/01, §1): the city map, faded, and one search box. */
export function LandingPage() {
  const navigate = useNavigate()
  // Remounting the search box with an example fills it and opens its suggestions.
  const [example, setExample] = useState({ text: '', n: 0 })
  const parcels = useAsync('parcels', fetchParcelLayer)
  const features = useAsync('features', fetchMapFeatures)
  const health = useAsync('health', fetchHealth)
  // Examples come from the data being served, so they always find something.
  const examples = useAsync('examples', fetchExamples)
  const chips =
    examples.status === 'ready'
      ? [
          { tag: 'ID', text: examples.data.parcelId, mono: true, ai: false },
          { tag: 'Address', text: examples.data.address, mono: false, ai: false },
          { tag: '✦ AI', text: examples.data.prompt, mono: false, ai: true },
        ]
      : []

  const theme = useMapTheme((state) => state.theme)

  return (
    <MapProvider>
      <main className="landing">
        <div className="landing-map">
          <BlueprintMap
            parcels={parcels.status === 'ready' ? parcels.data : null}
            features={features.status === 'ready' ? features.data : null}
            selectedId={null}
            onSelect={(id) => id && navigate(`/parcel/${id}`)}
            initialView={LANDING_VIEW}
            theme={theme}
          />
        </div>
        <div className="landing-fade" aria-hidden="true" />

        <header className="landing-header">
          <BrandMark />
          <div className="landing-header-end">
            {health.status === 'ready' && health.data.illustrative && (
              <span className="badge-illustrative">Illustrative data</span>
            )}
            <Link className="button-secondary" to="/search">
              Open the map
            </Link>
          </div>
        </header>

        <section className="landing-hero">
          <p className="landing-kicker">Pittsburgh · Site screening</p>
          <h1 className="landing-title">What can you build here?</h1>
          <p className="landing-sub">Screen any lot in the city in under a minute.</p>
          <Omnibox
            key={example.n}
            variant="hero"
            initialText={example.text}
            autoOpen={example.n > 0}
          />
          <div className="landing-examples" hidden={chips.length === 0}>
            <span>Try</span>
            {chips.map((ex) => (
              <button
                key={ex.text}
                type="button"
                className="example-chip"
                onClick={() => setExample((prev) => ({ text: ex.text, n: prev.n + 1 }))}
              >
                <span className={ex.ai ? 'example-tag is-ai' : 'example-tag'}>{ex.tag}</span>
                <span className={ex.mono ? 'mono' : undefined}>{ex.text}</span>
              </button>
            ))}
          </div>
          <p className="landing-hint">
            <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 3l14 8-6 2-2 6z" />
            </svg>
            Or click any lot on the map
          </p>
        </section>

        <MapControls show3d={false} />
      </main>
    </MapProvider>
  )
}
