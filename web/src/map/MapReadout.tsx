import { useMap } from '@vis.gl/react-maplibre'
import { useEffect, useState } from 'react'
import { MAP_ID, type MapView } from './BlueprintMap'
import { formatCoordinates, scaleBar } from './readout'

/**
 * Coordinates of the map center and a dashed scale bar, bottom center. It follows the map
 * itself (once per frame at most), so moving the map re-renders only this readout.
 */
export function MapReadout({ initial }: { initial: MapView }) {
  const map = useMap()[MAP_ID]
  const [view, setView] = useState(initial)

  useEffect(() => {
    if (!map) return
    let frame = 0
    const update = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const c = map.getCenter()
        setView({ longitude: c.lng, latitude: c.lat, zoom: map.getZoom() })
      })
    }
    update()
    map.on('move', update)
    return () => {
      cancelAnimationFrame(frame)
      map.off('move', update)
    }
  }, [map])

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
