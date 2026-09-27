/**
 * What did the user type into the search box? (docs/05-ai-search.md, "Detection")
 *
 * Mirrors api/src/navigator_api/search/detect.py for instant feedback; both are tested
 * against fixtures/search/detect_cases.json.
 */

export type DetectedKind = 'parcel_id' | 'address' | 'description' | 'empty'
export type IdFormat = 'county' | 'block_lot'

export interface Detection {
  kind: DetectedKind
  format: IdFormat | null
}

// Dashed or compact, complete or partial (autocomplete from 6 characters).
const COUNTY_ID = /^\d{4}-?[A-Z](-?\d{0,5}(-?\d{0,4}(-?\d{0,2})?)?)?$/i
const BLOCK_LOT = /^\d{1,3}-[A-Z]-\d{1,4}[A-Z]?$/i
const STREET_SUFFIXES =
  'st|street|ave|avenue|blvd|boulevard|rd|road|dr|drive|way|ln|lane|pl|place|ct|court|' +
  'ter|terrace|pkwy|hwy|cir|circle'
// A house number, then a street suffix within the next few words.
const ADDRESS = new RegExp(`^\\d+[A-Z]?\\s+(\\w+\\s+){0,4}(${STREET_SUFFIXES})\\b`, 'i')
const MIN_ID_CHARS = 6
// Starts like an address ("123 sam"): look it up before treating it as a description.
const HOUSE_NUMBER = /^\d+[A-Z]?\s+[A-Z]/i
// A street without a house number ("Kentucky Ave"): look it up for the lots on that street.
const STREET_NAME = new RegExp(`^([A-Z][\\w'.-]*\\s+){1,3}(${STREET_SUFFIXES})\\.?$`, 'i')

export function detect(text: string): Detection {
  const value = text.trim()
  if (!value) return { kind: 'empty', format: null }
  if (BLOCK_LOT.test(value)) return { kind: 'parcel_id', format: 'block_lot' }
  if (value.length >= MIN_ID_CHARS && COUNTY_ID.test(value)) {
    return { kind: 'parcel_id', format: 'county' }
  }
  if (ADDRESS.test(value)) return { kind: 'address', format: null }
  return { kind: 'description', format: null }
}

/**
 * IDs and addresses are looked up; so is ambiguous text: a house number first, or a street
 * name alone.
 */
export function shouldLookUp(text: string, detection: Detection): boolean {
  if (detection.kind === 'parcel_id' || detection.kind === 'address') return true
  const value = text.trim()
  return detection.kind === 'description' && (HOUSE_NUMBER.test(value) || STREET_NAME.test(value))
}
