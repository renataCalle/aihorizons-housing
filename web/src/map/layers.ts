import type { ExpressionSpecification, LayerSpecification } from 'maplibre-gl'

export const PARCELS = 'parcels'
export const FEATURES = 'map-features'
export const HATCH_IMAGE = 'hatch'
/** Layers that respond to clicks and hover. */
export const INTERACTIVE_LAYERS = ['parcels-fill']

/** Colors the map layers need, read from the design tokens in tokens.css. */
export interface MapPalette {
  cobalt: string
  sky: string
  orange: string
  unknown: string
  unknownTint: string
  ink: string
  lotFill: string
  lotLine: string
  assemblyTint: string
  building: string
  buildingTall: string
  skyTop: string
  paper: string
}

export function readPalette(root: Element = document.documentElement): MapPalette {
  const css = getComputedStyle(root)
  const token = (name: string) => css.getPropertyValue(name).trim()
  return {
    cobalt: token('--cobalt'),
    sky: token('--sky'),
    orange: token('--orange'),
    unknown: token('--unknown'),
    unknownTint: token('--unknown-tint'),
    ink: token('--ink'),
    lotFill: token('--lot-fill'),
    lotLine: token('--band-none-outline'),
    assemblyTint: token('--assembly-tint'),
    building: token('--building-3d'),
    buildingTall: token('--building-3d-tall'),
    skyTop: token('--sky-3d'),
    paper: token('--paper'),
  }
}

type Layer = LayerSpecification & { source: string; beforeId?: string }

/** Parcel layers, bottom to top: fills by band, unknown hatch, outlines, selection. */
export function parcelLayers(
  p: MapPalette,
  selectedId: string | null,
  hatch: boolean,
  hoveredId: string | null = null,
): Layer[] {
  // The selected lot shows its own band when it doesn't match the search (a match is drawn by
  // what the search ranks it on).
  const band: ExpressionSpecification = [
    'case',
    ['all', ['==', ['get', 'id'], selectedId ?? ''], ['==', ['get', 'band'], 'none']],
    ['get', 'ownBand'],
    ['get', 'band'],
  ]
  const layers: Layer[] = [
    {
      id: 'parcels-fill',
      type: 'fill',
      source: PARCELS,
      paint: {
        'fill-color': [
          'case',
          ['!=', ['get', 'assemblyId'], null],
          p.assemblyTint,
          [
            'match',
            band,
            'fast_track',
            p.cobalt,
            'conditions',
            p.sky,
            'high_risk',
            p.orange,
            'unknown',
            p.unknownTint,
            p.lotFill,
          ],
        ],
      },
    },
    {
      id: 'parcels-outline',
      type: 'line',
      source: PARCELS,
      paint: {
        'line-color': [
          'match',
          band,
          'none',
          p.lotLine,
          'unknown',
          p.unknown,
          '#ffffff',
        ],
        'line-width': ['match', band, 'none', 0.8, 1],
      },
    },
    {
      id: 'parcels-assembly',
      type: 'line',
      source: PARCELS,
      filter: ['!=', ['get', 'assemblyId'], null],
      paint: { 'line-color': p.cobalt, 'line-width': 1.5, 'line-dasharray': [2, 1.5] },
    },
    {
      id: 'parcels-hover',
      type: 'line',
      source: PARCELS,
      filter: ['==', ['get', 'id'], hoveredId ?? ''],
      paint: { 'line-color': p.cobalt, 'line-width': 2 },
    },
    {
      id: 'parcels-selected',
      type: 'line',
      source: PARCELS,
      filter: ['==', ['get', 'id'], selectedId ?? ''],
      paint: { 'line-color': p.ink, 'line-width': 2.5 },
    },
  ]
  if (hatch) {
    // After the outline in the list, so the outline exists when the hatch is added under it.
    layers.splice(2, 0, {
      id: 'parcels-hatch',
      type: 'fill',
      source: PARCELS,
      // Added once the pattern image exists, so pin it under the outlines and selection.
      beforeId: 'parcels-outline',
      filter: ['==', band, 'unknown'],
      paint: { 'fill-pattern': HATCH_IMAGE },
    })
  }
  return layers
}

/** Elevation tiles for the 3D view: Terrarium PNGs on AWS Open Data (no key). */
export const TERRAIN = 'terrain-dem'
export const TERRAIN_TILES = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
/** Pittsburgh's hills read better slightly raised. */
export const TERRAIN_EXAGGERATION = 1.3
/** Camera for the 3D view; every camera move keeps it while the view is on. */
export const CAMERA_3D = { pitch: 66, bearing: -25 }
/** Soft light from the upper left, so building sides stay pale rather than grey. */
export const LIGHT_3D = { anchor: 'viewport' as const, position: [1.5, 210, 30] as [number, number, number], intensity: 0.25, color: '#ffffff' }
export const CAMERA_2D = { pitch: 0, bearing: 0 }

/**
 * The 3D view's buildings: the basemap's building footprints raised to their mapped heights
 * (OpenMapTiles `render_height`), in the blueprint's pale blues.
 */
export function buildingExtrusion(p: MapPalette): Layer & { 'source-layer': string } {
  return {
    id: 'buildings-3d',
    type: 'fill-extrusion',
    source: 'openmaptiles',
    'source-layer': 'building',
    minzoom: 13,
    filter: ['!=', ['get', 'hide_3d'], true],
    paint: {
      'fill-extrusion-color': [
        'interpolate',
        ['linear'],
        ['coalesce', ['get', 'render_height'], 0],
        0,
        p.building,
        60,
        p.buildingTall,
      ],
      'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 0],
      'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
      // Heights arrive with the zoom 14 tiles: fade the buildings in as they do.
      'fill-extrusion-opacity': ['interpolate', ['linear'], ['zoom'], 13.5, 0, 14.5, 0.9],
      'fill-extrusion-vertical-gradient': true,
    },
  }
}

/** Sky and horizon haze for the tilted view, in the design's paper and sky blues. */
export function skySpec(p: MapPalette) {
  return {
    'sky-color': p.skyTop,
    'horizon-color': p.paper,
    'fog-color': p.paper,
    'sky-horizon-blend': 0.6,
    'horizon-fog-blend': 0.6,
    'fog-ground-blend': 0.8,
    'atmosphere-blend': 0,
  }
}

/** Transit stops, on top of the parcels. Parks and schools stay data-only until the Layers
 * toggle (M3); the basemap already draws real parks. */
export function featureLayers(p: MapPalette): Layer[] {
  return [
    {
      id: 'transit-stops',
      type: 'circle',
      source: FEATURES,
      filter: ['==', ['get', 'kind'], 'transit_stop'],
      paint: {
        'circle-radius': 5,
        'circle-color': '#ffffff',
        'circle-stroke-color': p.cobalt,
        'circle-stroke-width': 1.5,
        'circle-stroke-opacity': 0.7,
      },
    },
  ]
}
