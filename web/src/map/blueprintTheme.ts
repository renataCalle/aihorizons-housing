import type { LayerSpecification, StyleSpecification } from 'maplibre-gl'

/** Basemap palette from docs/02-design-system.md ("Map style"). */
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
 * The 3D view's basemap: Mapbox's "Standard" day palette, sampled from its rendering (cream
 * ground, green parks and woods, sky-blue water, lavender-grey roads). It gives the band
 * colours more contrast than the blueprint.
 */
export const STANDARD: BasemapPalette = {
  land: '#F0ECE2',
  park: '#BEE8B2',
  wood: '#B4E0A7',
  water: '#A7DAFA',
  waterLine: '#97CFF3',
  building: '#E4E0D7',
  buildingLine: '#D8D4CC',
  road: '#BFC5D6',
  roadCasing: '#B0B7CB',
  rail: '#C9CDD8',
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

/** Recolor a basemap style (OpenFreeMap Positron) into the light blueprint look. Pure. */
export function applyBlueprintTheme(style: StyleSpecification): StyleSpecification {
  const themed = structuredClone(style)
  const RULES = rules(BLUEPRINT)
  themed.layers = themed.layers.map((layer) => {
    const rule = RULES.find((r) => r.match(layer))
    if (!rule) return layer
    const next = { ...layer } as LayerSpecification & { paint?: Paint; layout?: Layout }
    if (rule.paint && 'paint' in next) next.paint = { ...next.paint, ...kept(next, rule.paint) }
    if (rule.layout) next.layout = { ...next.layout, ...rule.layout }
    return next as LayerSpecification
  })
  return themed
}

/**
 * The paint changes that turn an already themed map into `palette`, layer by layer: what the
 * 3D view applies to the live map (and undoes on the way out). Layout is left as it is.
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
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': BLUEPRINT.land } }],
}
