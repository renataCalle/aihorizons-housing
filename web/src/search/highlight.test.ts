import { describe, expect, it } from 'vitest'
import { formatCountyId, splitMatch } from './highlight'

describe('formatCountyId', () => {
  it('adds dashes to a compact county ID', () => {
    expect(formatCountyId('0055A00137000000')).toBe('0055-A-00137-0000-00')
  })

  it('leaves anything else alone', () => {
    expect(formatCountyId('55-A-137')).toBe('55-A-137')
  })
})

describe('splitMatch', () => {
  it('highlights a dashed prefix typed dashed or compact', () => {
    expect(splitMatch('0000-X-00000-0000-00', '0000-X-00000')).toEqual([
      '0000-X-00000',
      '-0000-00',
    ])
    expect(splitMatch('0000-X-00000-0000-00', '0000x00')).toEqual(['0000-X-00', '000-0000-00'])
  })

  it('highlights an address prefix ignoring case', () => {
    expect(splitMatch('123 Sample St', '123 sam')).toEqual(['123 Sam', 'ple St'])
  })

  it('highlights nothing when the text does not start with the query', () => {
    expect(splitMatch('205 Example Ave', 'example')).toEqual(['', '205 Example Ave'])
  })
})
