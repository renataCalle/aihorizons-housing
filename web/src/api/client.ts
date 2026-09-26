/** HTTP transport only. Responses are untyped here; adapters.ts turns them into view models. */

const BASE = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function getJson(path: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(`${BASE}${path}`, { signal, headers: { Accept: 'application/json' } })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null
    const detail = typeof body?.detail === 'string' ? body.detail : response.statusText
    throw new ApiError(response.status, detail)
  }
  return response.json()
}
