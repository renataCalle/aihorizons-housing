import { useMap } from '@vis.gl/react-maplibre'
import { MAP_ID } from './BlueprintMap'

interface Props {
  show3d?: boolean
  /** The 3D view is on */
  view3d?: boolean
  onToggle3d?: () => void
}

/** 3D view toggle and zoom, bottom right. */
export function MapControls({ show3d = true, view3d = false, onToggle3d }: Props) {
  const maps = useMap()
  const map = maps[MAP_ID]

  return (
    <div className="map-controls glass" role="group" aria-label="Map controls">
      {show3d && (
        <>
          <button
            type="button"
            className="map-control map-control-3d"
            aria-label="3D view"
            aria-pressed={view3d}
            disabled={!onToggle3d}
            onClick={onToggle3d}
          >
            {view3d ? '2D' : '3D'}
          </button>
          <div className="map-controls-divider" />
        </>
      )}
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
