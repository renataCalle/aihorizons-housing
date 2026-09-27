import {
  Layer,
  Map as MapGL,
  Marker,
  Source,
  useMap,
  type MapLayerMouseEvent,
} from '@vis.gl/react-maplibre'
import type { StyleSpecification } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { MapFeatures, ParcelLayer } from '../models/map'
import { applyBlueprintTheme, FALLBACK_STYLE } from './blueprintTheme'
import { Crosshair } from './Crosshair'
import { hatchPattern } from './hatch'
import {
  FEATURES,
  featureLayers,
  HATCH_IMAGE,
  INTERACTIVE_LAYERS,
  PARCELS,
  parcelLayers,
  buildingExtrusion,
  CAMERA_2D,
  CAMERA_3D,
  LIGHT_3D,
  readPalette,
  skySpec,
  TERRAIN,
  TERRAIN_EXAGGERATION,
  TERRAIN_TILES,
} from './layers'
import { ringCenter } from './readout'

const BASEMAP_URL = 'https://tiles.openfreemap.org/styles/positron'

export const MAP_ID = 'main'

export interface MapView {
  longitude: number
  latitude: number
  zoom: number
}

interface Props {
  parcels: ParcelLayer | null
  features: MapFeatures | null
  selectedId: string | null
  onSelect: (parcelId: string | null) => void
  initialView: MapView
  hoveredId?: string | null
  onHover?: (parcelId: string | null) => void
  /** Show transit stops (the Layers menu). */
  showTransit?: boolean
  /** 3D view: real buildings and terrain, camera tilted; lots stay coloured on the ground */
  view3d?: boolean
  /** Extra sources, layers and markers drawn over the parcels. */
  children?: ReactNode
}

/** Load the basemap once and recolor it; fall back to plain paper when it can't load. */
function useBlueprintStyle(): StyleSpecification | null {
  const [style, setStyle] = useState<StyleSpecification | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch(BASEMAP_URL, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
      .then((raw: StyleSpecification) => setStyle(applyBlueprintTheme(raw)))
      .catch(() => {
        if (!controller.signal.aborted) setStyle(FALLBACK_STYLE)
      })
    return () => controller.abort()
  }, [])
  return style
}

export function BlueprintMap({
  parcels,
  features,
  selectedId,
  onSelect,
  initialView,
  hoveredId = null,
  onHover,
  showTransit = false,
  view3d = false,
  children,
}: Props) {
  const style = useBlueprintStyle()
  const palette = useMemo(() => readPalette(), [])
  const [hatchReady, setHatchReady] = useState(false)
  const [hovering, setHovering] = useState(false)

  const selectedCenter = useMemo(() => {
    const feature = parcels?.features.find((f) => f.properties.id === selectedId)
    return feature ? ringCenter(feature.geometry) : null
  }, [parcels, selectedId])

  const layers = useMemo(
    () => parcelLayers(palette, selectedId, hatchReady, hoveredId),
    [palette, selectedId, hatchReady, hoveredId],
  )
  const overlays = useMemo(() => featureLayers(palette), [palette])
  const buildings = useMemo(() => buildingExtrusion(palette), [palette])
  const sky = useMemo(() => skySpec(palette), [palette])

  if (!style) return <div className="map-canvas map-loading" aria-hidden="true" />

  return (
    <MapGL
      id={MAP_ID}
      initialViewState={initialView}
      mapStyle={style}
      minZoom={11}
      maxZoom={20}
      style={{ position: 'absolute', inset: 0 }}
      attributionControl={{ compact: true }}
      interactiveLayerIds={INTERACTIVE_LAYERS}
      maxPitch={70}
      terrain={view3d ? { source: TERRAIN, exaggeration: TERRAIN_EXAGGERATION } : undefined}
      sky={view3d ? sky : undefined}
      light={view3d ? LIGHT_3D : undefined}
      cursor={hovering ? 'pointer' : 'grab'}
      onLoad={(e) => {
        const map = e.target
        if (!map.hasImage(HATCH_IMAGE)) {
          map.addImage(HATCH_IMAGE, hatchPattern(palette.unknown, palette.unknownTint))
        }
        setHatchReady(true)
      }}
      onMouseMove={(e: MapLayerMouseEvent) => {
        const id = e.features?.[0]?.properties?.id
        setHovering(typeof id === 'string')
        if (onHover && (typeof id === 'string' ? id : null) !== hoveredId) {
          onHover(typeof id === 'string' ? id : null)
        }
      }}
      onMouseLeave={() => {
        setHovering(false)
        onHover?.(null)
      }}
      onClick={(e: MapLayerMouseEvent) => {
        const id = e.features?.[0]?.properties?.id
        onSelect(typeof id === 'string' ? id : null)
      }}
    >
      {parcels && (
        <Source id={PARCELS} type="geojson" data={parcels}>
          {layers.map((layer) => (
            <Layer key={layer.id} {...layer} />
          ))}
        </Source>
      )}
      {features && (
        <Source id={FEATURES} type="geojson" data={features}>
          {overlays.map((layer) => (
            <Layer
              key={layer.id}
              {...layer}
              layout={{ visibility: showTransit ? 'visible' : 'none' }}
            />
          ))}
        </Source>
      )}
      {view3d && (
        <>
          <Source
            id={TERRAIN}
            type="raster-dem"
            tiles={[TERRAIN_TILES]}
            encoding="terrarium"
            tileSize={256}
            maxzoom={15}
          />
          <Layer {...buildings} />
        </>
      )}
      {children}
      <TiltCamera view3d={view3d} />
      {selectedCenter && (
        <Marker longitude={selectedCenter[0]} latitude={selectedCenter[1]} anchor="center">
          <Crosshair />
        </Marker>
      )}
    </MapGL>
  )
}

/** Tilt and turn the camera for the 3D view, and back to flat for the map. */
function TiltCamera({ view3d }: { view3d: boolean }) {
  const { current: map } = useMap()
  useEffect(() => {
    // A fit to the searched area or a glide to the selection already carries the tilt.
    if (!map || map.isMoving()) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    // Buildings carry heights from zoom 14: come close enough to read them as a city.
    map.easeTo({
      ...(view3d ? CAMERA_3D : CAMERA_2D),
      zoom: view3d ? Math.max(map.getZoom(), 15) : map.getZoom(),
      duration: reduce ? 0 : 1200,
    })
  }, [map, view3d])
  return null
}
