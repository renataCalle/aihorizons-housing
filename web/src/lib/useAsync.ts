import { useEffect, useState } from 'react'

export type AsyncState<T> =
  | { status: 'loading'; stale: T | null }
  | { status: 'error'; error: Error; stale: T | null }
  | { status: 'ready'; data: T }

/**
 * Run `load` whenever `key` changes; aborts the previous request. While a new key loads,
 * `stale` holds the last result, so screens can keep showing it instead of flashing empty.
 */
export function useAsync<T>(key: string, load: (signal: AbortSignal) => Promise<T>): AsyncState<T> {
  const [state, setState] = useState<{ key: string; value: AsyncState<T>; last: T | null }>({
    key,
    value: { status: 'loading', stale: null },
    last: null,
  })

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal).then(
      (data) => setState({ key, value: { status: 'ready', data }, last: data }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        const value = error instanceof Error ? error : new Error(String(error))
        setState((prev) => ({
          key,
          value: { status: 'error', error: value, stale: prev.last },
          last: prev.last,
        }))
      },
    )
    return () => controller.abort()
    // `load` is a new function each render; the request only depends on `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return state.key === key ? state.value : { status: 'loading', stale: state.last }
}
