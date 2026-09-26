import type { Evidence } from '../models/evidence'
import type { Health } from '../models/health'
import type { MapFeatures, ParcelLayer } from '../models/map'
import type { SiteReport } from '../models/report'
import { toEvidence, toHealth, toMapFeatures, toParcelLayer, toSiteReport } from './adapters'
import { getJson } from './client'

export { ApiError } from './client'

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  return toHealth(await getJson('/api/health', signal))
}

export async function fetchSiteReport(parcelId: string, signal?: AbortSignal): Promise<SiteReport> {
  return toSiteReport(await getJson(`/api/parcels/${encodeURIComponent(parcelId)}`, signal))
}

export async function fetchEvidence(evidenceId: string, signal?: AbortSignal): Promise<Evidence> {
  return toEvidence(await getJson(`/api/evidence/${encodeURIComponent(evidenceId)}`, signal))
}

export async function fetchParcelLayer(signal?: AbortSignal): Promise<ParcelLayer> {
  return toParcelLayer(await getJson('/api/map/parcels', signal))
}

export async function fetchMapFeatures(signal?: AbortSignal): Promise<MapFeatures> {
  return toMapFeatures(await getJson('/api/map/features', signal))
}
