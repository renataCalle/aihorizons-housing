import { DEFAULT_FILTERS, type Filters } from '../models/filters'

/** Filters in the URL (`?f=`): only the fields that differ from the defaults, base64url JSON. */
export function encodeFilters(filters: Filters): string {
  const changed = Object.fromEntries(
    Object.entries(filters).filter(
      ([key, value]) =>
        JSON.stringify(value) !== JSON.stringify(DEFAULT_FILTERS[key as keyof Filters]),
    ),
  )
  if (Object.keys(changed).length === 0) return ''
  const bytes = new TextEncoder().encode(JSON.stringify(changed))
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

/** `?f=` for no changes at all: base64url of "{}". */
export const NO_FILTERS = 'e30'

/**
 * `?f=` for a search. Next to a query (`?q=`) it is never left out, even with every filter
 * removed: a missing `f` means "read the query", which would bring its filters back.
 */
export function filterParam(filters: Filters, hasQuery: boolean): string | null {
  return encodeFilters(filters) || (hasQuery ? NO_FILTERS : null)
}

/** Back to filters; null when the parameter is missing or unreadable (a hand-edited link). */
export function decodeFilters(encoded: string | null): Filters | null {
  if (!encoded) return null
  try {
    const base64 = encoded.replace(/-/g, '+').replace(/_/g, '/')
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0))
    const changed = JSON.parse(new TextDecoder().decode(bytes)) as Partial<Filters>
    const known = Object.fromEntries(
      Object.entries(changed).filter(([key]) => key in DEFAULT_FILTERS),
    )
    return { ...DEFAULT_FILTERS, ...known }
  } catch {
    return null
  }
}
