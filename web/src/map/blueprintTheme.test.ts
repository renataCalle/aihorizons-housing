import type { LayerSpecification, StyleSpecification } from 'maplibre-gl'
import { describe, expect, it } from 'vitest'
import { applyBlueprintTheme, basemapPaint, BLUEPRINT, STANDARD } from './blueprintTheme'

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

const style: StyleSpecification = { version: 8, sources: {}, layers }

function layer(themed: StyleSpecification, layerId: string): any {
  return themed.layers.find((l) => l.id === layerId)
}

describe('applyBlueprintTheme', () => {
  const themed = applyBlueprintTheme(style)

  it('paints land, parks, water and buildings in blueprint blues', () => {
    expect(layer(themed, 'background').paint['background-color']).toBe(BLUEPRINT.land)
    expect(layer(themed, 'park').paint['fill-color']).toBe(BLUEPRINT.park)
    expect(layer(themed, 'water').paint['fill-outline-color']).toBe(BLUEPRINT.waterLine)
    expect(layer(themed, 'building').paint['fill-color']).toBe(BLUEPRINT.building)
  })

  it('makes roads white with pale casings, keeping their widths', () => {
    expect(layer(themed, 'highway_minor').paint).toEqual({
      'line-color': BLUEPRINT.road,
      'line-opacity': 1,
      'line-width': 2,
    })
    expect(layer(themed, 'highway_major_casing').paint['line-color']).toBe(BLUEPRINT.roadCasing)
  })

  it('hides shields and uppercases place labels', () => {
    expect(layer(themed, 'road_shield_us').layout.visibility).toBe('none')
    const label = layer(themed, 'label_city')
    expect(label.layout['text-transform']).toBe('uppercase')
    expect(label.layout['text-field']).toBe('{name}')
    expect(label.paint['text-color']).toBe(BLUEPRINT.label)
  })

  it('recolors street names without uppercasing them', () => {
    const name = layer(themed, 'highway-name-minor')
    expect(name.paint['text-color']).toBe(BLUEPRINT.label)
    expect(name.layout['text-transform']).toBeUndefined()
  })

  it('leaves unknown layers alone and never mutates the input', () => {
    expect(layer(themed, 'mystery').paint['fill-color']).toBe('#123456')
    expect(layer(style, 'background').paint['background-color']).toBe('#f8f4f0')
  })
})

describe('basemapPaint', () => {
  const changes = basemapPaint(applyBlueprintTheme(style).layers, STANDARD)
  const paintOf = (layerId: string) => changes.find((c) => c.layer === layerId)?.paint

  it('recolours the same layers in the Standard palette', () => {
    expect(paintOf('background')).toEqual({ 'background-color': STANDARD.land })
    expect(paintOf('water')).toEqual({
      'fill-color': STANDARD.water,
      'fill-outline-color': STANDARD.waterLine,
    })
    expect(paintOf('highway_minor')?.['line-color']).toBe(STANDARD.road)
  })

  it('changes only paint the layer type has, and leaves unmatched layers alone', () => {
    expect(paintOf('label_city')).toEqual({
      'text-color': STANDARD.label,
      'text-halo-color': STANDARD.land,
    })
    expect(paintOf('mystery')).toBeUndefined()
    expect(paintOf('road_shield_us')).toBeUndefined()
  })
})
