import { Layer, Marker, Source, useMap } from '@vis.gl/react-maplibre'
import type { Polygon, Position } from 'geojson'
import { useEffect, useMemo, useState, type RefObject } from 'react'
import type { MapFeatures } from '../models/map'
import type { SearchResult } from '../models/search'
import { MAP_ID } from './BlueprintMap'
import { CAMERA_2D, CAMERA_3D } from './layers'

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

/** "01", "02" … on the top results. Clicking one selects its lot, like clicking the lot. */
export function RankTags({
  results,
  onSelect,
}: {
  results: SearchResult[]
  onSelect: (parcelId: string) => void
}) {
  return results.slice(0, MAX_TAGS).map((r) => (
    <Marker
      key={r.parcel.id}
      longitude={r.parcel.centroid[0]}
      latitude={r.parcel.centroid[1]}
      anchor="bottom-left"
      offset={[6, -6]}
    >
      <button
        type="button"
        className={r.rank === 1 ? 'rank-tag is-first' : 'rank-tag'}
        aria-label={`Rank ${r.rank}: ${r.parcel.name}`}
        // The map also hears clicks on its markers: keep it from reading this one as a click
        // on empty map (which clears the selection).
        onMouseDown={(e) => e.nativeEvent.stopImmediatePropagation()}
        onClick={(e) => {
          e.stopPropagation()
          onSelect(r.parcel.id)
        }}
      >
        {String(r.rank).padStart(2, '0')}
      </button>
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
export function FitToAreas({
  features,
  areas,
  view3d = false,
}: {
  features: MapFeatures
  areas: string[]
  view3d?: boolean
}) {
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
    const padding = { top: 110, bottom: 80, left: 420, right: 360 }
    if (view3d) {
      // A whole neighborhood seen tilted is too far out to show buildings: go to street level
      // over its middle instead.
      const center: [number, number] = [
        (Math.min(...lons) + Math.max(...lons)) / 2,
        (Math.min(...lats) + Math.max(...lats)) / 2,
      ]
      map.easeTo({ center, zoom: 15.5, padding, duration: 1200, ...CAMERA_3D })
      return
    }
    const fit = () =>
      map.fitBounds(
        [
          [Math.min(...lons), Math.min(...lats)],
          [Math.max(...lons), Math.max(...lats)],
        ],
        { padding, duration: 600, maxZoom: 17.5, ...CAMERA_2D },
      )
    // Coming back from 3D: bounds can't be fitted while the camera is tilted, or with the
    // padding the 3D move left on the map, so level out and clear it first.
    if (map.getPitch() > 0) {
      map.once('moveend', fit)
      map.easeTo({ ...CAMERA_2D, padding: { top: 0, right: 0, bottom: 0, left: 0 }, duration: 500 })
      return () => {
        map.off('moveend', fit)
      }
    }
    fit()
  }, [map, features, key, view3d])
  return null
}

export interface Padding {
  top: number
  bottom: number
  left: number
  right: number
}

/** Glide to the selected parcel, keeping it clear of the panels around the map. */
export function FlyToSelection({
  center,
  padding,
  view3d = false,
}: {
  center: [number, number] | null
  padding: Padding
  view3d?: boolean
}) {
  const map = useMap()[MAP_ID]
  const key = center ? center.join(',') : ''
  const pad = `${padding.top},${padding.right},${padding.bottom},${padding.left}`
  useEffect(() => {
    if (!map || !key) return
    const [lon, lat] = key.split(',').map(Number)
    const [top, right, bottom, left] = pad.split(',').map(Number)
    map.easeTo({
      center: [lon, lat],
      zoom: Math.max(map.getZoom(), 17),
      padding: { top, right, bottom, left },
      duration: 700,
      ...(view3d ? CAMERA_3D : CAMERA_2D),
    })
  }, [map, key, pad, view3d])
  return null
}
