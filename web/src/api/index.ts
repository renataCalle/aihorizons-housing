import type { Evidence } from '../models/evidence'
import type { Health } from '../models/health'
import type { MapFeatures, ParcelLayer } from '../models/map'
import type { Program, SiteReport } from '../models/report'
import type { Filters } from '../models/filters'
import type {
  Examples,
  LookupResult,
  Neighborhood,
  ParseResult,
  SearchResponse,
} from '../models/search'
import {
  toEvidence,
  toExamples,
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

/** The report; with `program`, the engine scores that building instead of its own pick. */
export async function fetchSiteReport(
  parcelId: string,
  signal?: AbortSignal,
  program?: Program | null,
): Promise<SiteReport> {
  const path = `/api/parcels/${encodeURIComponent(parcelId)}${programQuery(program)}`
  return toSiteReport(await getJson(path, signal))
}

function programQuery(program?: Program | null): string {
  const query = new URLSearchParams()
  if (program) {
    query.set('product_type', program.productType)
    if (program.units !== null) query.set('units', String(program.units))
  }
  return query.size ? `?${query}` : ''
}

/** One finding or the approvals option of the report for the same `program`. */
export async function fetchEvidence(
  parcelId: string,
  evidenceId: string,
  signal?: AbortSignal,
  program?: Program | null,
): Promise<Evidence> {
  const path = `/api/parcels/${encodeURIComponent(parcelId)}/evidence/${encodeURIComponent(evidenceId)}`
  return toEvidence(await getJson(`${path}${programQuery(program)}`, signal))
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

export async function fetchExamples(signal?: AbortSignal): Promise<Examples> {
  return toExamples(await getJson('/api/examples', signal))
}
