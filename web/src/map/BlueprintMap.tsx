import {
  Layer,
  Map as MapGL,
  Marker,
  Source,
  type MapLayerMouseEvent,
  type ViewStateChangeEvent,
} from '@vis.gl/react-maplibre'
import type { StyleSpecification } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useState } from 'react'
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
  readPalette,
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
  onViewChange?: (view: MapView) => void
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
  onViewChange,
}: Props) {
  const style = useBlueprintStyle()
  const palette = useMemo(() => readPalette(), [])
  const [hatchReady, setHatchReady] = useState(false)
  const [hovering, setHovering] = useState(false)

  const selectedCenter = useMemo(() => {
    const feature = parcels?.features.find((f) => f.properties.id === selectedId)
    return feature ? ringCenter(feature.geometry) : null
  }, [parcels, selectedId])

  const layers = parcelLayers(palette, selectedId, hatchReady)
  const overlays = featureLayers(palette)

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
      cursor={hovering ? 'pointer' : 'grab'}
      onLoad={(e) => {
        const map = e.target
        if (!map.hasImage(HATCH_IMAGE)) {
          map.addImage(HATCH_IMAGE, hatchPattern(palette.unknown, palette.unknownTint))
        }
        setHatchReady(true)
      }}
      onMouseMove={(e: MapLayerMouseEvent) => setHovering((e.features?.length ?? 0) > 0)}
      onMouseLeave={() => setHovering(false)}
      onClick={(e: MapLayerMouseEvent) => {
        const id = e.features?.[0]?.properties?.id
        onSelect(typeof id === 'string' ? id : null)
      }}
      onMove={(e: ViewStateChangeEvent) =>
        onViewChange?.({
          longitude: e.viewState.longitude,
          latitude: e.viewState.latitude,
          zoom: e.viewState.zoom,
        })
      }
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
            <Layer key={layer.id} {...layer} />
          ))}
        </Source>
      )}
      {selectedCenter && (
        <Marker longitude={selectedCenter[0]} latitude={selectedCenter[1]} anchor="center">
          <Crosshair />
        </Marker>
      )}
    </MapGL>
  )
}
