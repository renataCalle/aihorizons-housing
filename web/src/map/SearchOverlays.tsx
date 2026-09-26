import { Layer, Marker, Source, useMap } from '@vis.gl/react-maplibre'
import type { Polygon, Position } from 'geojson'
import { useEffect, useMemo, useState, type RefObject } from 'react'
import type { MapFeatures } from '../models/map'
import type { SearchResult } from '../models/search'
import { MAP_ID } from './BlueprintMap'

const WORLD: Position[] = [
  [-180, -85],
  [180, -85],
  [180, 85],
  [-180, 85],
  [-180, -85],
]

/** Dims the city outside the searched neighborhoods and outlines them (MapBase.dc.html). */
export function AreaOverlay({ features, areas }: { features: MapFeatures; areas: string[] }) {
  const polygons = useMemo(
    () =>
      features.features.filter(
        (f) =>
          f.properties.kind === 'neighborhood' &&
          f.properties.name !== null &&
          areas.includes(f.properties.name) &&
          f.geometry.type === 'Polygon',
      ),
    [features, areas],
  )
  if (polygons.length === 0) return null

  const rings = polygons.map((f) => (f.geometry as Polygon).coordinates[0])
  const dim = {
    type: 'Feature' as const,
    properties: {},
    geometry: { type: 'Polygon' as const, coordinates: [WORLD, ...rings] },
  }
  const outline = { type: 'FeatureCollection' as const, features: polygons }

  return (
    <>
      <Source id="area-dim" type="geojson" data={dim}>
        <Layer
          id="area-dim"
          type="fill"
          beforeId="parcels-fill"
          paint={{ 'fill-color': '#f5f8fd', 'fill-opacity': 0.66 }}
        />
      </Source>
      <Source id="area-boundary" type="geojson" data={outline}>
        <Layer
          id="area-boundary"
          type="line"
          paint={{ 'line-color': '#1d3fd6', 'line-width': 1.5, 'line-dasharray': [3, 2] }}
        />
      </Source>
      {polygons.map((f, i) => {
        // Label at the northernmost corner, like the mockup's chip on the boundary.
        const top = rings[i].reduce((a, b) => (b[1] > a[1] ? b : a))
        return (
          <Marker key={f.properties.name} longitude={top[0]} latitude={top[1]} anchor="bottom">
            <span className="area-label">{f.properties.name}</span>
          </Marker>
        )
      })}
    </>
  )
}

const MAX_TAGS = 9

/** "01", "02" … on the top results. */
export function RankTags({ results }: { results: SearchResult[] }) {
  return results.slice(0, MAX_TAGS).map((r) => (
    <Marker
      key={r.parcel.id}
      longitude={r.parcel.centroid[0]}
      latitude={r.parcel.centroid[1]}
      anchor="bottom-left"
      offset={[6, -6]}
    >
      <span className={r.rank === 1 ? 'rank-tag is-first' : 'rank-tag'}>
        {String(r.rank).padStart(2, '0')}
      </span>
    </Marker>
  ))
}

/** Dashed leader from the selected parcel to the inspector card, in screen space. */
export function LeaderLine({
  at,
  cardRef,
}: {
  at: [number, number] | null
  cardRef: RefObject<HTMLElement | null>
}) {
  const map = useMap()[MAP_ID]
  const [points, setPoints] = useState<[number, number, number, number] | null>(null)

  useEffect(() => {
    if (!map || !at) return
    const update = () => {
      const card = cardRef.current?.getBoundingClientRect()
      const canvas = map.getCanvas().getBoundingClientRect()
      if (!card) return
      const p = map.project(at)
      setPoints([canvas.left + p.x, canvas.top + p.y, card.left, card.top + 160])
    }
    update()
    map.on('move', update)
    window.addEventListener('resize', update)
    return () => {
      map.off('move', update)
      window.removeEventListener('resize', update)
    }
  }, [map, at, cardRef])

  if (!at || !points) return null
  const [x1, y1, x2, y2] = points
  return (
    <svg className="leader-line" aria-hidden="true">
      <line x1={x1} y1={y1} x2={x2} y2={y2} />
      <circle cx={x1} cy={y1} r="3" />
      <circle cx={x2} cy={y2} r="3" />
    </svg>
  )
}

/** Zoom to the searched neighborhoods, leaving room for the panels on both sides. */
export function FitToAreas({ features, areas }: { features: MapFeatures; areas: string[] }) {
  const map = useMap()[MAP_ID]
  const key = areas.join('|')
  useEffect(() => {
    if (!map || !key) return
    const names = key.split('|')
    const points = features.features
      .filter((f) => f.properties.kind === 'neighborhood' && names.includes(f.properties.name ?? ''))
      .flatMap((f) => (f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] : []))
    if (points.length === 0) return
    const lons = points.map((p) => p[0])
    const lats = points.map((p) => p[1])
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: { top: 110, bottom: 80, left: 420, right: 360 }, duration: 600, maxZoom: 17.5 },
    )
  }, [map, features, key])
  return null
}
