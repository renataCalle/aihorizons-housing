import type { MapView } from './BlueprintMap'
import { formatCoordinates, scaleBar } from './readout'

/** Coordinates of the map center and a dashed scale bar, bottom center. */
export function MapReadout({ view }: { view: MapView }) {
  const bar = scaleBar(view.latitude, view.zoom)
  const width = Math.round(bar.px)
  return (
    <div className="map-readout glass" aria-label="Map position">
      <span>{formatCoordinates(view.longitude, view.latitude)}</span>
      <svg width={width + 6} height="10" viewBox={`0 0 ${width + 6} 10`} aria-hidden="true">
        <circle cx="3" cy="5" r="2.5" fill="var(--cobalt)" />
        <line
          x1="6"
          y1="5"
          x2={width}
          y2="5"
          stroke="var(--cobalt)"
          strokeWidth="1"
          strokeDasharray="4 3"
        />
        <circle cx={width + 3} cy="5" r="2.5" fill="var(--cobalt)" />
      </svg>
      <span>{bar.label}</span>
    </div>
  )
}
