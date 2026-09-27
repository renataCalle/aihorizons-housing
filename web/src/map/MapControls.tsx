import { useMap } from '@vis.gl/react-maplibre'
import { MAP_ID } from './BlueprintMap'
import { THEMES, type MapThemeId } from './themes'

interface Props {
  show3d?: boolean
  /** The 3D view is on */
  view3d?: boolean
  onToggle3d?: () => void
  /** Map style: the button switches between Blueprint and Standard */
  themeId?: MapThemeId
  onTheme?: (id: MapThemeId) => void
}

/** 3D view toggle and zoom, bottom right. */
export function MapControls({
  show3d = true,
  view3d = false,
  onToggle3d,
  themeId,
  onTheme,
}: Props) {
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
      {themeId && onTheme && (
        <>
          <button
            type="button"
            className="map-control map-control-style"
            aria-label="Standard map style"
            aria-pressed={themeId === 'standard'}
            title={`Map style: ${THEMES[themeId].label}`}
            onClick={() => onTheme(themeId === 'standard' ? 'blueprint' : 'standard')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 3a9 9 0 1 0 0 18c1.1 0 1.6-.9 1.2-1.8-.5-1 .2-2.2 1.3-2.2H17a4 4 0 0 0 4-4c0-5-4-10-9-10z" />
              <circle cx="7.5" cy="11" r="1" />
              <circle cx="10.5" cy="7" r="1" />
              <circle cx="15" cy="7.5" r="1" />
            </svg>
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
