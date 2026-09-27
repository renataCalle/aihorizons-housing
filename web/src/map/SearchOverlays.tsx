import { Layer, Marker, Source, useMap } from '@vis.gl/react-maplibre'
import type { Polygon, Position } from 'geojson'
import { useEffect, useMemo, useState, type RefObject } from 'react'
import type { MapFeatures } from '../models/map'
import type { SearchResult } from '../models/search'
import { MAP_ID } from './BlueprintMap'
import { groupTags } from './rankTags'
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

/**
 * "01", "02" … on the top results. Tags that would overlap merge into one pill that lists all
 * their numbers (rankTags.ts), so every tag stays visible; the pill splits as the map zooms
 * in. Each number selects its lot, like clicking the lot, and outlines it on hover or focus.
 */
export function RankTags({
  results,
  onSelect,
  onHover,
}: {
  results: SearchResult[]
  onSelect: (parcelId: string) => void
  onHover?: (parcelId: string | null) => void
}) {
  const map = useMap()[MAP_ID]
  const top = useMemo(() => results.slice(0, MAX_TAGS), [results])
  const byId = useMemo(() => new Map(top.map((r) => [r.parcel.id, r])), [top])
  // The groups as a string, so an unchanged grouping doesn't re-render on every frame.
  const [grouping, setGrouping] = useState<string | null>(null)

  useEffect(() => {
    if (!map) return
    let frame = 0
    const update = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const points = top.map((r) => {
          const { x, y } = map.project(r.parcel.centroid)
          return { id: r.parcel.id, x, y }
        })
        setGrouping(groupTags(points).map((g) => g.ids.join(',')).join('|'))
      })
    }
    update()
    map.on('move', update)
    return () => {
      map.off('move', update)
      cancelAnimationFrame(frame)
    }
  }, [map, top])

  const groups = grouping ? grouping.split('|').map((g) => g.split(',')) : top.map((r) => [r.parcel.id])
  return groups.map((ids) => {
    const members = ids.map((id) => byId.get(id)).filter((r): r is SearchResult => !!r)
    const lead = members[0]
    if (!lead) return null
    const tag = (r: SearchResult) => (
      <button
        key={r.parcel.id}
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
        onMouseEnter={() => onHover?.(r.parcel.id)}
        onMouseLeave={() => onHover?.(null)}
        onFocus={() => onHover?.(r.parcel.id)}
        onBlur={() => onHover?.(null)}
      >
        {String(r.rank).padStart(2, '0')}
      </button>
    )
    return (
      <Marker
        key={ids.join(',')}
        longitude={lead.parcel.centroid[0]}
        latitude={lead.parcel.centroid[1]}
        anchor="bottom-left"
        offset={[6, -6]}
      >
        {members.length === 1 ? (
          tag(lead)
        ) : (
          <span
            className="rank-group"
            role="group"
            aria-label={`Ranks ${members.map((r) => r.rank).join(', ')}, close together`}
          >
            {members.map(tag)}
          </span>
        )}
      </Marker>
    )
  })
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
