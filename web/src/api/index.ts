import type { Evidence } from '../models/evidence'
import type { Health } from '../models/health'
import type { SiteReport } from '../models/report'
import { toEvidence, toHealth, toSiteReport } from './adapters'
import { getJson } from './client'

export { ApiError } from './client'

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  return toHealth(await getJson('/api/health', signal))
}

export async function fetchSiteReport(parcelId: string, signal?: AbortSignal): Promise<SiteReport> {
  const path = `/api/parcels/${encodeURIComponent(parcelId)}/analysis`
  return toSiteReport(await getJson(path, signal))
}

export async function fetchEvidence(evidenceId: string, signal?: AbortSignal): Promise<Evidence> {
  return toEvidence(await getJson(`/api/evidence/${encodeURIComponent(evidenceId)}`, signal))
}
