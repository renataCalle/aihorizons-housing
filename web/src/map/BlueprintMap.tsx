import {
  Layer,
  Map as MapGL,
  Marker,
  Source,
  useMap,
  type MapLayerMouseEvent,
} from '@vis.gl/react-maplibre'
import type { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { MapFeatures, ParcelLayer } from '../models/map'
import { applyMapTheme, basemapPaint, FALLBACK_STYLE } from './blueprintTheme'
import { Crosshair } from './Crosshair'
import { hatchPattern } from './hatch'
import {
  FEATURES,
  featureLayers,
  HATCH_IMAGE,
  INTERACTIVE_LAYERS,
  PARCELS,
  parcelLayers,
  BUILDINGS_3D,
  buildingExtrusion,
  CAMERA_2D,
  CAMERA_3D,
  light3d,
  readPalette,
  skySpec,
} from './layers'
import { ringCenter } from './readout'
import type { MapTheme } from './themes'

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
  /** 3D view: camera tilted, and the theme's buildings raised; lots stay on the ground */
  view3d?: boolean
  /** Basemap and band colours; switching recolours the live map without reloading it */
  theme: MapTheme
  /** The lot whose report is open: drawn in the strong risk colour */
  reportId?: string | null
  /** Extra sources, layers and markers drawn over the parcels. */
  children?: ReactNode
}

/**
 * Load the basemap once, themed in `theme` as it is on first render; fall back to plain paper
 * when it can't load. Later theme switches recolour the live map (ThemeBasemap).
 */
function useBlueprintStyle(theme: MapTheme): StyleSpecification | null {
  const [style, setStyle] = useState<StyleSpecification | null>(null)
  const [initial] = useState(theme)
  useEffect(() => {
    const controller = new AbortController()
    fetch(BASEMAP_URL, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
      .then((raw: StyleSpecification) => setStyle(applyMapTheme(raw, initial.basemap)))
      .catch(() => {
        if (!controller.signal.aborted) setStyle(FALLBACK_STYLE)
      })
    return () => controller.abort()
  }, [initial])
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
  theme,
  reportId = null,
  children,
}: Props) {
  const style = useBlueprintStyle(theme)
  const palette = useMemo(() => readPalette(), [])
  const [hatchReady, setHatchReady] = useState(false)
  const [hovering, setHovering] = useState(false)

  const selectedCenter = useMemo(() => {
    const feature = parcels?.features.find((f) => f.properties.id === selectedId)
    return feature ? ringCenter(feature.geometry) : null
  }, [parcels, selectedId])

  const layers = useMemo(
    () =>
      parcelLayers(palette, {
        bands: theme.bands,
        lotLine: theme.lotLine,
        selectedId,
        hoveredId,
        reportId,
        hatch: hatchReady,
        view3d,
      }),
    [palette, theme, selectedId, hoveredId, reportId, hatchReady, view3d],
  )
  const overlays = useMemo(() => featureLayers(palette), [palette])
  const buildings = useMemo(
    () => (theme.buildings ? buildingExtrusion(theme.buildings) : null),
    [theme.buildings],
  )
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
      sky={view3d ? sky : undefined}
      light={view3d && theme.buildings ? light3d(theme.buildings.light) : undefined}
      cursor={hovering ? 'pointer' : 'grab'}
      onLoad={(e) => {
        const map = e.target
        if (!map.hasImage(HATCH_IMAGE)) {
          const { unknownLine, unknownTint } = theme.bands
          map.addImage(HATCH_IMAGE, hatchPattern(unknownLine, unknownTint))
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
      {view3d && buildings && <Layer {...buildings} />}
      {children}
      <ThemeBasemap theme={theme} />
      <TiltCamera view3d={view3d} />
      <BuildingsOnTop active={view3d && !!buildings} />
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

type PaintKey = Parameters<MapLibreMap['setPaintProperty']>[1]
type PaintValue = Parameters<MapLibreMap['setPaintProperty']>[2]

/**
 * Recolour the live basemap when the theme changes, without reloading the style: the data
 * layers, the selection and the camera stay as they are. The unknown hatch follows too.
 */
function ThemeBasemap({ theme }: { theme: MapTheme }) {
  const { current: ref } = useMap()
  useEffect(() => {
    const map = ref?.getMap()
    if (!map) return
    const apply = () => {
      for (const { layer, paint } of basemapPaint(map.getStyle().layers, theme.basemap)) {
        for (const [prop, value] of Object.entries(paint)) {
          map.setPaintProperty(layer, prop as PaintKey, value as PaintValue)
        }
      }
      const { unknownLine, unknownTint } = theme.bands
      if (map.hasImage(HATCH_IMAGE)) {
        map.updateImage(HATCH_IMAGE, hatchPattern(unknownLine, unknownTint))
      }
    }
    if (map.isStyleLoaded()) apply()
    else map.once('idle', apply)
    return () => {
      map.off('idle', apply)
    }
  }, [ref, theme])
  return null
}

/**
 * In the 3D view, keep the buildings above the lots: layers draw in the order they were added,
 * and the lots (or a hatch or overlay) can be added after the buildings, e.g. when the page
 * opens straight into 3D. Move the buildings back to the top whenever a layer is added.
 */
function BuildingsOnTop({ active }: { active: boolean }) {
  const { current: ref } = useMap()
  useEffect(() => {
    const map = ref?.getMap()
    if (!map || !active) return
    const keepOnTop = () => {
      const order = map.getLayersOrder()
      if (map.getLayer(BUILDINGS_3D) && order[order.length - 1] !== BUILDINGS_3D) {
        map.moveLayer(BUILDINGS_3D)
      }
    }
    map.on('styledata', keepOnTop)
    keepOnTop()
    return () => {
      map.off('styledata', keepOnTop)
    }
  }, [ref, active])
  return null
}
