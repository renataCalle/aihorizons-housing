import type { LayerSpecification, StyleSpecification } from 'maplibre-gl'
import { describe, expect, it } from 'vitest'
import { applyMapTheme, BLUEPRINT, STANDARD } from './blueprintTheme'

const layers = [
  { id: 'background', type: 'background', paint: { 'background-color': '#f8f4f0' } },
  { id: 'park', type: 'fill', source: 'omt', 'source-layer': 'park', paint: { 'fill-color': '#d8e8c8' } },
  { id: 'water', type: 'fill', source: 'omt', 'source-layer': 'water', paint: { 'fill-color': '#aad' } },
  { id: 'building', type: 'fill', source: 'omt', 'source-layer': 'building', paint: {} },
  { id: 'highway_minor', type: 'line', source: 'omt', 'source-layer': 'transportation', paint: { 'line-color': '#ddd', 'line-width': 2 } },
  { id: 'highway_major_casing', type: 'line', source: 'omt', 'source-layer': 'transportation', paint: { 'line-color': '#ccc' } },
  { id: 'road_shield_us', type: 'symbol', source: 'omt', 'source-layer': 'transportation_name', layout: {} },
  { id: 'highway-name-minor', type: 'symbol', source: 'omt', 'source-layer': 'transportation_name', paint: { 'text-color': '#666' }, layout: {} },
  { id: 'label_city', type: 'symbol', source: 'omt', 'source-layer': 'place', paint: { 'text-color': '#333' }, layout: { 'text-field': '{name}' } },
  { id: 'mystery', type: 'fill', source: 'omt', 'source-layer': 'mystery', paint: { 'fill-color': '#123456' } },
] as LayerSpecification[]

const style: StyleSpecification = {
  version: 8,
  sources: { openmaptiles: { type: 'vector', url: 'https://example.test/tiles' } },
  layers,
}

function layer(themed: StyleSpecification, layerId: string): any {
  return themed.layers.find((l) => l.id === layerId)
}

describe('applyMapTheme', () => {
  const themed = applyMapTheme(style)

  it('paints land, parks, water and buildings in the Standard palette', () => {
    expect(layer(themed, 'background').paint['background-color']).toBe(STANDARD.land)
    expect(layer(themed, 'park').paint['fill-color']).toBe(STANDARD.park)
    expect(layer(themed, 'water').paint['fill-outline-color']).toBe(STANDARD.waterLine)
    expect(layer(themed, 'building').paint['fill-color']).toBe(STANDARD.building)
  })

  it('recolours roads and casings, keeping their widths', () => {
    expect(layer(themed, 'highway_minor').paint).toEqual({
      'line-color': STANDARD.road,
      'line-opacity': 1,
      'line-width': 2,
    })
    expect(layer(themed, 'highway_major_casing').paint['line-color']).toBe(STANDARD.roadCasing)
  })

  it('hides shields and uppercases place labels', () => {
    expect(layer(themed, 'road_shield_us').layout.visibility).toBe('none')
    const label = layer(themed, 'label_city')
    expect(label.layout['text-transform']).toBe('uppercase')
    expect(label.layout['text-field']).toBe('{name}')
    expect(label.paint['text-color']).toBe(STANDARD.label)
  })

  it('recolors street names without uppercasing them', () => {
    const name = layer(themed, 'highway-name-minor')
    expect(name.paint['text-color']).toBe(STANDARD.label)
    expect(name.layout['text-transform']).toBeUndefined()
  })

  it('leaves unknown layers alone and never mutates the input', () => {
    expect(layer(themed, 'mystery').paint['fill-color']).toBe('#123456')
    expect(layer(style, 'background').paint['background-color']).toBe('#f8f4f0')
  })
})

describe('applyMapTheme extras', () => {
  it('adds a grass layer under the buildings', () => {
    const ids = applyMapTheme(style).layers.map((l) => l.id)
    expect(ids.indexOf('landcover-grass')).toBe(ids.indexOf('building') - 1)
    expect(layer(applyMapTheme(style), 'landcover-grass').paint['fill-color']).toBe(STANDARD.park)
  })

  it('still themes in the blueprint palette on request', () => {
    const blueprint = applyMapTheme(style, BLUEPRINT)
    expect(layer(blueprint, 'background').paint['background-color']).toBe(BLUEPRINT.land)
  })
})
