import type { Evidence } from '../models/evidence'
import type { Health } from '../models/health'
import type { MapFeatures, ParcelLayer } from '../models/map'
import type { SiteReport } from '../models/report'
import type { Filters } from '../models/filters'
import type { LookupResult, Neighborhood, ParseResult, SearchResponse } from '../models/search'
import {
  toEvidence,
  toHealth,
  toLookup,
  toApiFilters,
  toMapFeatures,
  toNeighborhoods,
  toParcelLayer,
  toParseResult,
  toSearchResponse,
  toSiteReport,
} from './adapters'
import { getJson, postJson } from './client'

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

export async function fetchLookup(text: string, signal?: AbortSignal): Promise<LookupResult> {
  return toLookup(await getJson(`/api/lookup?q=${encodeURIComponent(text)}`, signal))
}

export async function fetchSearch(filters: Filters, signal?: AbortSignal): Promise<SearchResponse> {
  return toSearchResponse(await postJson('/api/search', toApiFilters(filters), signal))
}

export async function fetchParse(
  text: string,
  current: Filters | null,
  signal?: AbortSignal,
): Promise<ParseResult> {
  const body = { text, current_filters: current ? toApiFilters(current) : null }
  return toParseResult(await postJson('/api/search/parse', body, signal))
}

export async function fetchNeighborhoods(signal?: AbortSignal): Promise<Neighborhood[]> {
  return toNeighborhoods(await getJson('/api/neighborhoods', signal))
}
