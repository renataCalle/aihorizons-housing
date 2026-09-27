import type { ExpressionSpecification, LayerSpecification } from 'maplibre-gl'
import type { BandColors, BuildingColors } from './themes'

export const PARCELS = 'parcels'
export const FEATURES = 'map-features'
export const HATCH_IMAGE = 'hatch'
/** Layers that respond to clicks and hover. */
export const INTERACTIVE_LAYERS = ['parcels-fill']

/** Colours the map layers need beyond the theme's (themes.ts), read from tokens.css. */
export interface MapPalette {
  cobalt: string
  ink: string
  assemblyTint: string
  skyTop: string
  paper: string
}

export function readPalette(root: Element = document.documentElement): MapPalette {
  const css = getComputedStyle(root)
  const token = (name: string) => css.getPropertyValue(name).trim()
  return {
    cobalt: token('--cobalt'),
    ink: token('--ink'),
    assemblyTint: token('--assembly-tint'),
    skyTop: token('--sky-3d'),
    paper: token('--paper'),
  }
}

type Layer = LayerSpecification & { source: string; beforeId?: string }

/** What the parcel layers draw: the theme's colours and which lots stand out. */
export interface ParcelStyle {
  bands: BandColors
  /** Lines between lots that aren't candidates */
  lotLine: string
  selectedId: string | null
  hoveredId?: string | null
  /** The lot whose report is open: drawn in the strong risk colour, not the soft one */
  reportId?: string | null
  /** The hatch image for unknown lots has been added */
  hatch: boolean
  /** 3D view: the selected lot is raised SELECTED_LOT_HEIGHT_M in its band colour */
  view3d?: boolean
}

/** Parcel layers, bottom to top: fills by band, unknown hatch, outlines, selection. */
export function parcelLayers(p: MapPalette, s: ParcelStyle): Layer[] {
  const { bands, selectedId, hoveredId = null, reportId = null, hatch } = s
  // The selected lot shows its own band when it doesn't match the search (a match is drawn by
  // what the search ranks it on).
  const band: ExpressionSpecification = [
    'case',
    ['all', ['==', ['get', 'id'], selectedId ?? ''], ['==', ['get', 'band'], 'none']],
    ['get', 'ownBand'],
    ['get', 'band'],
  ]
  // High-risk lots are soft on the map; the one whose report is open keeps the strong colour.
  const strongRisk: ExpressionSpecification = ['==', ['get', 'id'], reportId ?? '']
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
            bands.fast,
            'conditions',
            bands.conditions,
            'high_risk',
            ['case', strongRisk, bands.risk, bands.riskSoftFill],
            'unknown',
            bands.unknownTint,
            'transparent',
          ],
        ],
        'fill-opacity': 0.85,
      },
    },
    {
      id: 'parcels-outline',
      type: 'line',
      source: PARCELS,
      paint: {
        // A thin white line between adjacent scored lots; soft risk lots get their own outline.
        'line-color': [
          'match',
          band,
          'none',
          s.lotLine,
          'unknown',
          bands.unknownLine,
          'high_risk',
          ['case', strongRisk, '#ffffff', bands.riskSoftOutline],
          '#ffffff',
        ],
        'line-width': [
          'match',
          band,
          'none',
          0.8,
          'high_risk',
          ['case', strongRisk, 0.75, 1.5],
          0.75,
        ],
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
  if (s.view3d && selectedId) {
    // Before the selection outline, so the outline stays on top at the block's base.
    layers.splice(layers.length - 1, 0, {
      id: 'parcels-selected-3d',
      type: 'fill-extrusion',
      source: PARCELS,
      filter: ['all', ['==', ['get', 'id'], selectedId], ['!=', band, 'none']],
      paint: {
        'fill-extrusion-color': [
          'match',
          band,
          'fast_track',
          bands.fast,
          'conditions',
          bands.conditions,
          'high_risk',
          bands.risk,
          bands.unknownLine,
        ],
        'fill-extrusion-height': SELECTED_LOT_HEIGHT_M,
        'fill-extrusion-opacity': 1,
      },
    })
  }
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

/** Camera for the 3D view; every camera move keeps it while the view is on. */
export const CAMERA_3D = { pitch: 66, bearing: -25 }
/** Soft light from the upper left, so building sides stay pale rather than grey. */
/** The 3D view's light: white, from the upper left of the viewport, at the theme's strength. */
export function light3d(intensity: number) {
  return {
    anchor: 'viewport' as const,
    position: [1.5, 210, 30] as [number, number, number],
    color: '#FFFFFF',
    intensity,
  }
}

/** The selected lot's height in the 3D view, in metres. Other lots stay flat. */
export const SELECTED_LOT_HEIGHT_M = 3
export const CAMERA_2D = { pitch: 0, bearing: 0 }

export const BUILDINGS_3D = 'buildings-3d'

/**
 * The 3D view's buildings: the basemap's building footprints raised to their mapped heights
 * (OpenMapTiles `render_height`), in the theme's colours: low buildings in `low`, blending
 * to `high` for tall ones. Solid, so lots behind a building never show through.
 */
export function buildingExtrusion(c: BuildingColors): Layer & { 'source-layer': string } {
  return {
    id: BUILDINGS_3D,
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
        c.low,
        20,
        c.low,
        70,
        c.high,
      ],
      'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 0],
      'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
      // Heights arrive with the zoom 14 tiles: fade the buildings in as they do.
      'fill-extrusion-opacity': ['interpolate', ['linear'], ['zoom'], 13.5, 0, 14.5, 1],
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
