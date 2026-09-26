import type { LayerSpecification, StyleSpecification } from 'maplibre-gl'

/** Basemap palette from docs/02-design-system.md ("Map style"). */
export const BLUEPRINT = {
  land: '#EEF4FB',
  park: '#F3F7FD',
  water: '#D3E3F7',
  waterLine: '#B4CCEC',
  building: '#E3ECF8',
  buildingLine: '#C5D7EF',
  road: '#FFFFFF',
  roadCasing: '#D5E2F4',
  rail: '#C9D9F0',
  label: '#6A84B8',
} as const

type Paint = Record<string, unknown>
type Layout = Record<string, unknown>

interface Rule {
  match: (layer: LayerSpecification) => boolean
  paint?: Paint
  layout?: Layout
}

const id = (pattern: RegExp) => (layer: LayerSpecification) => pattern.test(layer.id)

/** First matching rule wins. Layers no rule matches are left as they are. */
const RULES: Rule[] = [
  // Road shields and POI icons are noise on a screening map.
  { match: id(/shield|^airport$/), layout: { visibility: 'none' } },
  {
    match: id(/^highway-name/),
    paint: { 'text-color': BLUEPRINT.label, 'text-halo-color': BLUEPRINT.land },
    layout: { 'text-letter-spacing': 0.08 },
  },
  { match: id(/^background$/), paint: { 'background-color': BLUEPRINT.land } },
  { match: id(/^park$/), paint: { 'fill-color': BLUEPRINT.park } },
  { match: id(/^(landuse|landcover|aeroway-area)/), paint: { 'fill-color': BLUEPRINT.land } },
  {
    match: id(/^water$/),
    paint: { 'fill-color': BLUEPRINT.water, 'fill-outline-color': BLUEPRINT.waterLine },
  },
  { match: id(/^waterway$/), paint: { 'line-color': BLUEPRINT.waterLine } },
  {
    match: id(/^building$/),
    paint: { 'fill-color': BLUEPRINT.building, 'fill-outline-color': BLUEPRINT.buildingLine },
  },
  { match: id(/casing$/), paint: { 'line-color': BLUEPRINT.roadCasing } },
  { match: id(/^highway_path$/), paint: { 'line-color': BLUEPRINT.rail, 'line-dasharray': [2, 2] } },
  { match: id(/^highway_minor$/), paint: { 'line-color': BLUEPRINT.road, 'line-opacity': 1 } },
  { match: id(/^(highway|tunnel|road|aeroway)/), paint: { 'line-color': BLUEPRINT.road } },
  { match: id(/^railway/), paint: { 'line-color': BLUEPRINT.rail } },
  { match: id(/^boundary/), paint: { 'line-color': BLUEPRINT.rail } },
  {
    match: (layer) => layer.type === 'symbol',
    paint: { 'text-color': BLUEPRINT.label, 'text-halo-color': BLUEPRINT.land },
    layout: { 'text-transform': 'uppercase', 'text-letter-spacing': 0.14 },
  },
]

/** Recolor a basemap style (OpenFreeMap Positron) into the light blueprint look. Pure. */
export function applyBlueprintTheme(style: StyleSpecification): StyleSpecification {
  const themed = structuredClone(style)
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
