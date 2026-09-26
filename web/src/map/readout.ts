import type { Geometry, Position } from 'geojson'

const EARTH_CIRCUMFERENCE_M = 40_075_016.686
const FEET_PER_METER = 3.28084
const NICE_FEET = [10, 20, 50, 100, 200, 500, 1000, 2000]
const NICE_MILES = [0.5, 1, 2, 5, 10, 20]

/** Feet per screen pixel at a latitude and MapLibre zoom (512px tiles). */
export function feetPerPixel(lat: number, zoom: number): number {
  const metersPerPixel =
    (EARTH_CIRCUMFERENCE_M * Math.cos((lat * Math.PI) / 180)) / (512 * 2 ** zoom)
  return metersPerPixel * FEET_PER_METER
}

/** The longest round distance whose bar fits in `maxPx`: "200 FT", "0.5 MI". */
export function scaleBar(lat: number, zoom: number, maxPx = 110): { label: string; px: number } {
  const fpp = feetPerPixel(lat, zoom)
  const feet = [...NICE_FEET].reverse().find((f) => f / fpp <= maxPx)
  if (feet !== undefined && feet / fpp >= maxPx / 5) return { label: `${feet} FT`, px: feet / fpp }
  const miles = [...NICE_MILES].reverse().find((m) => (m * 5280) / fpp <= maxPx) ?? NICE_MILES[0]
  return { label: `${miles} MI`, px: (miles * 5280) / fpp }
}

/** "40.4052° N · 79.9433° W" */
export function formatCoordinates(lon: number, lat: number): string {
  const ns = lat >= 0 ? 'N' : 'S'
  const ew = lon >= 0 ? 'E' : 'W'
  return `${Math.abs(lat).toFixed(4)}° ${ns} · ${Math.abs(lon).toFixed(4)}° ${ew}`
}

/** Center of a polygon's outer ring (vertex average): where the crosshair sits. */
export function ringCenter(geometry: Geometry): [number, number] | null {
  let ring: Position[] | undefined
  if (geometry.type === 'Polygon') ring = geometry.coordinates[0]
  else if (geometry.type === 'MultiPolygon') ring = geometry.coordinates[0]?.[0]
  else if (geometry.type === 'Point') return [geometry.coordinates[0], geometry.coordinates[1]]
  if (!ring || ring.length === 0) return null
  const points = ring.length > 1 && ring[0].every((v, i) => v === ring.at(-1)![i]) ? ring.slice(0, -1) : ring
  const lon = points.reduce((sum, p) => sum + p[0], 0) / points.length
  const lat = points.reduce((sum, p) => sum + p[1], 0) / points.length
  return [lon, lat]
}
