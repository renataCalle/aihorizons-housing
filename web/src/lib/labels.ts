import type { Band } from '../models/report'

/** Short band names for pills, list rows and legends. Sentence case (docs/01, copy rules). */
export const BAND_LABEL: Record<Band, string> = {
  fast_track: 'Fast track',
  conditions: 'Conditions',
  high_risk: 'High risk',
  unknown: 'Not scored',
}
