import type { FeatureCollection, Geometry } from 'geojson'
import type { Band } from './report'

/** 'none' = not a candidate: drawn as an outline only. */
export type MapBand = Band | 'none'

/** Properties on each parcel feature, as the map layers read them. */
export interface ParcelMapProps {
  id: string
  name: string
  band: MapBand
  score: number | null
  rank: number | null
  assemblyId: string | null
}

export type ParcelLayer = FeatureCollection<Geometry, ParcelMapProps>

export type MapFeatureKind = 'transit_stop' | 'park' | 'school' | 'neighborhood'

export type MapFeatures = FeatureCollection<Geometry, { kind: MapFeatureKind; name: string | null }>
