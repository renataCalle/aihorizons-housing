import type { LayerSpecification } from 'maplibre-gl'

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
            ['get', 'band'],
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
          ['get', 'band'],
          'none',
          p.lotLine,
          'unknown',
          p.unknown,
          '#ffffff',
        ],
        'line-width': ['match', ['get', 'band'], 'none', 0.8, 1],
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
    layers.splice(1, 0, {
      id: 'parcels-hatch',
      type: 'fill',
      source: PARCELS,
      // Added once the pattern image exists, so pin it under the outlines and selection.
      beforeId: 'parcels-outline',
      filter: ['==', ['get', 'band'], 'unknown'],
      paint: { 'fill-pattern': HATCH_IMAGE },
    })
  }
  return layers
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
