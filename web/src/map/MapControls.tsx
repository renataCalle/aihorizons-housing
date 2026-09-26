import { useMap } from '@vis.gl/react-maplibre'
import { MAP_ID } from './BlueprintMap'

/** 3D toggle (M5) and zoom, bottom right. */
export function MapControls() {
  const maps = useMap()
  const map = maps[MAP_ID]

  return (
    <div className="map-controls glass" role="group" aria-label="Map controls">
      <button
        type="button"
        className="map-control map-control-3d"
        aria-label="3D score view (coming soon)"
        disabled
      >
        3D
      </button>
      <div className="map-controls-divider" />
      <button
        type="button"
        className="map-control"
        aria-label="Zoom in"
        onClick={() => map?.zoomIn()}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </button>
      <button
        type="button"
        className="map-control"
        aria-label="Zoom out"
        onClick={() => map?.zoomOut()}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 12h14" />
        </svg>
      </button>
    </div>
  )
}
