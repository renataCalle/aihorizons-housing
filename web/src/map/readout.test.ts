import { describe, expect, it } from 'vitest'
import { feetPerPixel, formatCoordinates, ringCenter, scaleBar } from './readout'

describe('scale bar', () => {
  it('matches the known ground resolution', () => {
    // At the equator, zoom 0 with 512px tiles is about 78,271 m per pixel.
    expect(feetPerPixel(0, 0) / 3.28084).toBeCloseTo(78_271.5, 0)
  })

  it('picks a round distance that fits', () => {
    const bar = scaleBar(40.405, 16.5, 110)
    expect(bar.label).toMatch(/^\d+ FT$/)
    expect(bar.px).toBeLessThanOrEqual(110)
    expect(bar.px).toBeGreaterThan(22)
  })

  it('switches to miles when zoomed out', () => {
    expect(scaleBar(40.405, 11, 110).label).toMatch(/MI$/)
  })
})

describe('formatCoordinates', () => {
  it('formats Pittsburgh as north and west', () => {
    expect(formatCoordinates(-79.94331, 40.40521)).toBe('40.4052° N · 79.9433° W')
  })
})

describe('ringCenter', () => {
  it('averages the outer ring without double-counting the closing point', () => {
    const square = {
      type: 'Polygon' as const,
      coordinates: [
        [
          [0, 0],
          [2, 0],
          [2, 2],
          [0, 2],
          [0, 0],
        ],
      ],
    }
    expect(ringCenter(square)).toEqual([1, 1])
  })
})
