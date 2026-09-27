import type { LayerSpecification, StyleSpecification } from 'maplibre-gl'

/** The original blueprint palette from docs/02-design-system.md ("Map style"). */
export const BLUEPRINT = {
  land: '#EEF4FB',
  park: '#F3F7FD',
  wood: '#EEF4FB', // woods read as plain land in the blueprint
  water: '#D3E3F7',
  waterLine: '#B4CCEC',
  building: '#E3ECF8',
  buildingLine: '#C5D7EF',
  road: '#FFFFFF',
  roadCasing: '#D5E2F4',
  rail: '#C9D9F0',
  label: '#6A84B8',
} as const

/**
 * The Standard theme's basemap: Mapbox's "Standard" day palette, sampled from its rendering
 * (cream ground, green parks and woods, sky-blue water, lavender-grey roads), then softened by
 * blending each colour 20% toward the ground. Labels keep full strength for 4.5:1 contrast.
 */
export const STANDARD: BasemapPalette = {
  land: '#F0ECE2',
  park: '#C8E9BC',
  wood: '#C0E2B3',
  water: '#B6DEF5',
  waterLine: '#A9D5F0',
  building: '#E6E2D9',
  buildingLine: '#DDD9D0',
  road: '#C9CDD8',
  roadCasing: '#BDC2D0',
  rail: '#D1D3DA',
  label: '#56657E',
}

export type BasemapPalette = { [K in keyof typeof BLUEPRINT]: string }

type Paint = Record<string, unknown>
type Layout = Record<string, unknown>

interface Rule {
  match: (layer: LayerSpecification) => boolean
  paint?: Paint
  layout?: Layout
}

const id = (pattern: RegExp) => (layer: LayerSpecification) => pattern.test(layer.id)

/** First matching rule wins. Layers no rule matches are left as they are. */
const rules = (c: BasemapPalette): Rule[] => [
  // Road shields and POI icons are noise on a screening map.
  { match: id(/shield|^airport$/), layout: { visibility: 'none' } },
  {
    match: id(/^highway-name/),
    paint: { 'text-color': c.label, 'text-halo-color': c.land },
    layout: { 'text-letter-spacing': 0.08 },
  },
  { match: id(/^background$/), paint: { 'background-color': c.land } },
  { match: id(/^park$/), paint: { 'fill-color': c.park } },
  { match: id(/^landcover_wood$/), paint: { 'fill-color': c.wood } },
  { match: id(/^landcover-grass$/), paint: { 'fill-color': c.park } },
  { match: id(/^(landuse|landcover|aeroway-area)/), paint: { 'fill-color': c.land } },
  {
    match: id(/^water$/),
    paint: { 'fill-color': c.water, 'fill-outline-color': c.waterLine },
  },
  { match: id(/^waterway$/), paint: { 'line-color': c.waterLine } },
  {
    match: id(/^building$/),
    paint: { 'fill-color': c.building, 'fill-outline-color': c.buildingLine },
  },
  { match: id(/casing$/), paint: { 'line-color': c.roadCasing } },
  { match: id(/^highway_path$/), paint: { 'line-color': c.rail, 'line-dasharray': [2, 2] } },
  { match: id(/^highway_minor$/), paint: { 'line-color': c.road, 'line-opacity': 1 } },
  { match: id(/^(highway|tunnel|road|aeroway)/), paint: { 'line-color': c.road } },
  { match: id(/^railway/), paint: { 'line-color': c.rail } },
  { match: id(/^boundary/), paint: { 'line-color': c.rail } },
  {
    match: (layer) => layer.type === 'symbol',
    paint: { 'text-color': c.label, 'text-halo-color': c.land },
    layout: { 'text-transform': 'uppercase', 'text-letter-spacing': 0.14 },
  },
]

/**
 * Grass: the basemap tiles carry it, but the Positron style draws no layer for it. Added under
 * the buildings so lawns read green like parks.
 */
export function grassLayer(color: string): LayerSpecification {
  return {
    id: 'landcover-grass',
    type: 'fill',
    source: 'openmaptiles',
    'source-layer': 'landcover',
    filter: ['==', ['get', 'class'], 'grass'],
    paint: { 'fill-color': color },
  }
}

/**
 * Recolor a basemap style (OpenFreeMap Positron) into `palette`, keeping the blueprint's quiet
 * labels and hidden shields, and add a grass layer under the buildings. Pure.
 */
export function applyMapTheme(
  style: StyleSpecification,
  palette: BasemapPalette = STANDARD,
): StyleSpecification {
  const themed = structuredClone(style)
  const RULES = rules(palette)
  themed.layers = themed.layers.map((layer) => {
    const rule = RULES.find((r) => r.match(layer))
    if (!rule) return layer
    const next = { ...layer } as LayerSpecification & { paint?: Paint; layout?: Layout }
    if (rule.paint && 'paint' in next) next.paint = { ...next.paint, ...kept(next, rule.paint) }
    if (rule.layout) next.layout = { ...next.layout, ...rule.layout }
    return next as LayerSpecification
  })
  const building = themed.layers.findIndex((l) => l.id === 'building')
  if (building >= 0 && 'openmaptiles' in themed.sources) {
    themed.layers.splice(building, 0, grassLayer(palette.park))
  }
  return themed
}

/**
 * The paint changes that switch a themed map to `palette`, layer by layer: how a theme switch
 * recolours the live map without reloading it (the data layers and the selection stay put).
 */
export function basemapPaint(
  layers: LayerSpecification[],
  palette: BasemapPalette,
): { layer: string; paint: Paint }[] {
  const RULES = rules(palette)
  return layers.flatMap((layer) => {
    const rule = RULES.find((r) => r.match(layer))
    if (!rule?.paint || !('paint' in layer)) return []
    const paint = kept(layer, rule.paint)
    return Object.keys(paint).length ? [{ layer: layer.id, paint }] : []
  })
}

/** Only set paint properties that belong to the layer's type (fill-* on fills, etc.). */
function kept(layer: LayerSpecification, paint: Paint): Paint {
  const prefix = layer.type === 'symbol' ? 'text-' : `${layer.type}-`
  return Object.fromEntries(Object.entries(paint).filter(([key]) => key.startsWith(prefix)))
}

/** Used when the basemap can't load (offline): parcels still draw on plain paper. */
export const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': STANDARD.land } }],
}
