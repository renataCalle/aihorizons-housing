import { useEffect, useState } from 'react'

export type AsyncState<T> =
  | { status: 'loading' }
  | { status: 'error'; error: Error }
  | { status: 'ready'; data: T }

/** Run `load` whenever `key` changes; aborts the previous request. */
export function useAsync<T>(key: string, load: (signal: AbortSignal) => Promise<T>): AsyncState<T> {
  const [state, setState] = useState<{ key: string; value: AsyncState<T> }>({
    key,
    value: { status: 'loading' },
  })

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal).then(
      (data) => setState({ key, value: { status: 'ready', data } }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        const value = error instanceof Error ? error : new Error(String(error))
        setState({ key, value: { status: 'error', error: value } })
      },
    )
    return () => controller.abort()
    // `load` is a new function each render; the request only depends on `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return state.key === key ? state.value : { status: 'loading' }
}
