import type { Versions } from './report'

export interface Health {
  ok: boolean
  siteSource: string
  illustrative: boolean
  versions: Versions
}
