import { useEffect, useState } from 'react'
import { fetchLookup } from '../api'
import type { LookupMatch } from '../models/search'
import { shouldLookUp, type Detection } from './detect'

const DEBOUNCE_MS = 150

export type LookupState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; query: string; matches: LookupMatch[] }
  | { status: 'error' }

/** Parcel IDs and addresses are looked up as the user types; plain descriptions never are. */
export function useLookup(text: string, detection: Detection): LookupState {
  const [state, setState] = useState<LookupState>({ status: 'idle' })
  const query = text.trim()
  const lookable = shouldLookUp(text, detection)

  useEffect(() => {
    if (!lookable) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setState({ status: 'loading' })
      fetchLookup(query, controller.signal).then(
        (result) => setState({ status: 'ready', query, matches: result.matches }),
        () => {
          if (!controller.signal.aborted) setState({ status: 'error' })
        },
      )
    }, DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query, lookable])

  if (!lookable) return { status: 'idle' }
  // Until the debounced request answers for this exact text, show the previous results.
  return state
}
